from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME # Fixed import location
from django import forms
from django.core.exceptions import ValidationError
from .models import MerchantProduct, Merchant, MerchantCategory, MerchantCategoryExclusionRule
from accounts.models import Estate
from products.models import Product, Category
from .ImportConfigurationForm import ImportConfigurationForm
from django.urls import path
from .utils import get_user_merchant
from django.db.models import Q




admin.site.register(MerchantCategory)


@admin.register(MerchantCategoryExclusionRule)
class MerchantCategoryExclusionRuleAdmin(admin.ModelAdmin):
    list_display = ('merchant_category',)
    # filter_horizontal provides a nice side-by-side UI for Super Admins 
    # to select multiple product categories easily
    filter_horizontal = ('excluded_categories',)


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'estates', 'estates_backup')
    search_fields = ['store_name']
    fields = ['store_name', 'address', 'phone_number', 'email', 'category', 'staff_users', 'estates', 'estates_backup', 'brand_logo', 'image_preview']
    readonly_fields = ['estates', 'estates_backup', 'image_preview']

    def save_related(self, request, form, formsets, change):
        """
        Intercepts ManyToMany relation saving to ensure a user is only
        associated with one merchant at a time.
        """
        # 1. Allow Django Admin to process the form validation first
        super().save_related(request, form, formsets, change)
        
        # 2. Get the merchant instance being saved
        merchant = form.instance
        
        # 3. Get the list of staff users selected in the admin form for THIS merchant
        selected_staff = form.cleaned_data.get('staff_users', [])
        
        for user in selected_staff:
            # Find any other merchant where this user is currently a staff member
            other_merchants = Merchant.objects.filter(staff_users=user).exclude(pk=merchant.pk)
            
            for other_merchant in other_merchants:
                # Remove the user from the previous merchant
                other_merchant.staff_users.remove(user)
                
        # Note: No need to call merchant.save() here because super().save_related() 
        # already saved the current relationship. We just cleaned up the old ones!


# Custom Form to add validation rules for the merchant
class MerchantProductForm(forms.ModelForm):
    class Meta:
        model = MerchantProduct
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        
        # We need the current thread request to fetch the logged-in user's profile
        import inspect
        req = None
        for frame_record in inspect.stack():
            if frame_record[3] == 'get_response':
                req = frame_record[0].f_locals.get('request')
                break


            # --- EXISTING RULE: Prevent duplicates on creation ---
            if product and not self.instance.pk: 
                merchant = get_user_merchant(req.user)
                if merchant:
                    if MerchantProduct.objects.filter(merchant=merchant, product=product).exists():
                        raise ValidationError(
                            f"You are already selling '{product.name}'. Please search for it on your main inventory page to edit its price."
                        )
                        
        return cleaned_data



@admin.register(MerchantProduct)
class MerchantProductAdmin(admin.ModelAdmin):
    form = MerchantProductForm

    list_display = ('product', 'price', 'display', 'image_preview')
    search_fields = ('product__name', 'product__categories__name')
    autocomplete_fields = ['product'] 
    actions = ['import_all_global_products'] 



    def get_changelist_instance(self, request):
        """
        Safely configures editable properties on the core object instance.
        """
        if request.session.get('merchant_edit_mode', False):
            self.list_editable = ('price', 'display')
        else:
            self.list_editable = ()
        return super().get_changelist_instance(request)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('toggle-edit-mode/', self.admin_site.admin_view(self.toggle_edit_mode_view), name='merchantproduct_toggle_edit'),
            # Consolidate URLs into one unified configuration endpoint
            path('import-configuration/', self.admin_site.admin_view(self.import_configuration_view), name='merchantproduct_import_config'),
        ]
        return custom_urls + urls



    def toggle_edit_mode_view(self, request):
        """
        Toggles the edit mode state in the session and routes directly back into 
        the native change list generation view loop. This populates all 'formset' variables.
        """
        current_state = request.session.get('merchant_edit_mode', False)
        request.session['merchant_edit_mode'] = not current_state
        
        # We tell our template via a custom header parameter that this is an AJAX partial query
        request.META['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        
        # Re-route processing straight to the secure native engine
        return self.changelist_view(request)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        is_editing = request.session.get('merchant_edit_mode', False)
        extra_context['is_editing'] = is_editing

        # Capture the original response from the native Django Admin view
        response = super().changelist_view(request, extra_context=extra_context)
        
        # If this request was triggered by our AJAX toggle button, we pull out 
        # only the inner content form container instead of rendering the whole site shell again
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            # This allows us to extract the form section without a complex secondary partial template file
            response.template_name = 'admin/merchant_table_partial.html'
            
        return response


    def import_configuration_view(self, request):
        merchant = get_user_merchant(request.user)
        if not merchant:
            self.message_user(request, "Only registered merchants or staff can run this action.", messages.ERROR)
            return HttpResponseRedirect("../")
        
        if request.method == 'POST':
            # PASS MERCHANT HERE
            form = ImportConfigurationForm(request.POST, merchant=merchant)
            if form.is_valid():
                import_type = form.cleaned_data['import_type']
                excluded_categories = form.cleaned_data['excluded_categories']
                included_categories = form.cleaned_data['included_categories']
                
                import_with_price = form.cleaned_data['import_with_price']
                update_unpriced = form.cleaned_data['update_unpriced']
                overwrite_all_prices = form.cleaned_data['overwrite_all_prices']

                existing_product_ids = MerchantProduct.objects.filter(merchant=merchant).values_list('product_id', flat=True)
                
                if import_type == 'specific':
                    missing_products = Product.objects.filter(
                        categories__in=included_categories, package=False, display=True
                    ).exclude(id__in=existing_product_ids).distinct()
                    msg_prefix = "from selected categories"
                else:
                    missing_products = Product.objects.filter(
                        package=False, display=True
                    ).exclude(id__in=existing_product_ids)
                    
                    if excluded_categories.exists():
                        missing_products = missing_products.exclude(categories__in=excluded_categories)
                        
                    missing_products = missing_products.distinct()
                    msg_prefix = "from the global catalog"

                missing_count = missing_products.count()
                if missing_count > 0:
                    new_inventory_items = []
                    for prod in missing_products:
                        assigned_price = prod.price if import_with_price else None
                        assigned_display = True if import_with_price else False
                        
                        new_inventory_items.append(
                            MerchantProduct(merchant=merchant, product=prod, price=assigned_price, display=assigned_display)
                        )
                    MerchantProduct.objects.bulk_create(new_inventory_items)
                    self.message_user(request, f"✨ Success! Imported {missing_count} missing products {msg_prefix}.", messages.SUCCESS)
                else:
                    self.message_user(request, f"No new products found to import {msg_prefix}.", messages.INFO)

                # --- Update Logic Remains the same ---
                if overwrite_all_prices:
                    items_to_update = MerchantProduct.objects.filter(merchant=merchant).select_related('product')
                    update_count = items_to_update.count()
                    if update_count > 0:
                        for item in items_to_update:
                            item.price = item.product.price
                            item.display = True
                        MerchantProduct.objects.bulk_update(items_to_update, ['price', 'display'])
                        self.message_user(request, f"⚠️ Overwrote prices for all {update_count} products in your inventory.", messages.WARNING)

                elif update_unpriced:
                    items_to_update = MerchantProduct.objects.filter(merchant=merchant, price__isnull=True).select_related('product')
                    update_count = items_to_update.count()
                    if update_count > 0:
                        for item in items_to_update:
                            item.price = item.product.price
                            item.display = True
                        MerchantProduct.objects.bulk_update(items_to_update, ['price', 'display'])
                        self.message_user(request, f"✅ Updated prices for {update_count} previously unpriced products.", messages.SUCCESS)

                return HttpResponseRedirect("../")
        else:
            # PASS MERCHANT HERE TOO
            form = ImportConfigurationForm(merchant=merchant)

        context = {
            **self.admin_site.each_context(request), 
            'form': form, 
            'merchant': merchant, # Passed to template for friendly messaging
            'title': 'Import & Update Configuration', 
            'opts': self.model._meta
        }
        return render(request, 'admin/import_configuration.html', context)




    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
            
        merchant = get_user_merchant(request.user)
        if merchant:
            return qs.filter(merchant=merchant)
            
        # If they were removed from the merchant model, they see absolutely nothing
        return qs.none()


    def save_model(self, request, obj, form, change):
        merchant = get_user_merchant(request.user)
        if not request.user.is_superuser and merchant:
            obj.merchant = merchant
        super().save_model(request, obj, form, change)


    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if not request.user.is_superuser:
            if 'merchant' in fields:
                fields.remove('merchant')
        return fields
