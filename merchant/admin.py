from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.admin import SimpleListFilter
from django.utils.translation import gettext_lazy as _
from django.urls import path
from django.db.models import Q

from .models import MerchantProduct, Merchant, MerchantCategory, MerchantCategoryExclusionRule
from accounts.models import Estate
from products.models import Product, Category
from .ImportConfigurationForm import ImportConfigurationForm
from .utils import get_user_merchant


admin.site.register(MerchantCategory)

@admin.register(MerchantCategoryExclusionRule)
class MerchantCategoryExclusionRuleAdmin(admin.ModelAdmin):
    list_display = ('merchant_category',)
    filter_horizontal = ('excluded_categories',)


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'estates', 'estates_backup')
    search_fields = ['store_name']
    fields = ['store_name', 'address', 'phone_number', 'email', 'category', 'staff_users', 'estates', 'estates_backup', 'brand_logo', 'image_preview']
    readonly_fields = ['estates', 'estates_backup', 'image_preview']

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        merchant = form.instance
        selected_staff = form.cleaned_data.get('staff_users', [])
        
        for user in selected_staff:
            other_merchants = Merchant.objects.filter(staff_users=user).exclude(pk=merchant.pk)
            for other_merchant in other_merchants:
                other_merchant.staff_users.remove(user)


class MerchantProductForm(forms.ModelForm):
    class Meta:
        model = MerchantProduct
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        
        import inspect
        req = None
        for frame_record in inspect.stack():
            if frame_record[3] == 'get_response':
                req = frame_record[0].f_locals.get('request')
                break

        if product and not self.instance.pk: 
            merchant = get_user_merchant(req.user)
            if merchant:
                if MerchantProduct.objects.filter(merchant=merchant, product=product).exists():
                    raise ValidationError(
                        f"You are already selling '{product.name}'. Please search for it on your main inventory page to edit its price."
                    )
                    
        return cleaned_data


# --- NEW: Custom Filter to handle Superuser defaults and explicitly detect "All" clicks ---
class SuperuserMerchantFilter(SimpleListFilter):
    title = _('Store Name')
    parameter_name = 'merchant_id'

    def lookups(self, request, model_admin):
        # We only need this filter populated if they are a superuser
        if request.user.is_superuser:
            return [(m.id, m.store_name) for m in Merchant.objects.all()]
        return []

    def choices(self, changelist):
        # Override the default "All" button to pass an explicit parameter instead of removing it.
        yield {
            'selected': self.value() == 'all',
            'query_string': changelist.get_query_string({self.parameter_name: 'all'}, []),
            'display': _('All Stores (Clear Filter)'),
        }
        for lookup, title in self.lookup_choices:
            yield {
                'selected': self.value() == str(lookup),
                'query_string': changelist.get_query_string({self.parameter_name: lookup}, []),
                'display': title,
            }

    def queryset(self, request, queryset):
        val = self.value()
        
        # 1. User explicitly clicked "All Stores"
        if val == 'all':
            return queryset
        
        # 2. User actively selected a specific store from the right-hand menu
        if val:
            return queryset.filter(merchant_id=val)
            
        # 3. Default state (no parameter in URL): Show superuser's assigned store by default
        if request.user.is_superuser:
            merchant = get_user_merchant(request.user) or Merchant.objects.filter(staff_users=request.user).first()
            if merchant:
                return queryset.filter(merchant=merchant)
                
        return queryset



class CategoryFilter(SimpleListFilter):
    title = _('Category')  # Sets the display name in the admin panel sidebar
    parameter_name = 'category'

    def lookups(self, request, model_admin):
        # Fetch distinct category names. Replace Category with your actual Category model if imported differently.
        from .models import Category  
        return [(c.name, c.name) for c in Category.objects.all()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(product__categories__name=self.value())
        return queryset

    

@admin.register(MerchantProduct)
class MerchantProductAdmin(admin.ModelAdmin):
    form = MerchantProductForm
    list_display = ('product', 'price', 'display', 'store_name', 'categories', 'image_preview')
    search_fields = ('product__name', 'product__categories__name')
    autocomplete_fields = ['product'] 
    actions = ['import_all_global_products'] 

    def get_list_filter(self, request):
            """ Include Category filter for all users, add Store filter for superusers """
            filters = [CategoryFilter]
            if request.user.is_superuser:
                filters.append(SuperuserMerchantFilter)
            return tuple(filters)

    def get_changelist_instance(self, request):
        if request.session.get('merchant_edit_mode', False):
            self.list_editable = ('price', 'display')
        else:
            self.list_editable = ()
        return super().get_changelist_instance(request)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('toggle-edit-mode/', self.admin_site.admin_view(self.toggle_edit_mode_view), name='merchantproduct_toggle_edit'),
            path('import-configuration/', self.admin_site.admin_view(self.import_configuration_view), name='merchantproduct_import_config'),
        ]
        return custom_urls + urls

    def toggle_edit_mode_view(self, request):
        current_state = request.session.get('merchant_edit_mode', False)
        request.session['merchant_edit_mode'] = not current_state
        request.META['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        return self.changelist_view(request)

    def changelist_view(self, request, extra_context=None):
        # NOTE: Removed the buggy request.GET intercept here. The custom filter handles it now.
        extra_context = extra_context or {}
        is_editing = request.session.get('merchant_edit_mode', False)
        extra_context['is_editing'] = is_editing

        response = super().changelist_view(request, extra_context=extra_context)
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest':
            response.template_name = 'admin/merchant_table_partial.html'
            
        return response

    def import_configuration_view(self, request):
        merchant = get_user_merchant(request.user)
        if not merchant and request.user.is_superuser:
            merchant = Merchant.objects.filter(staff_users=request.user).first()

        if not merchant:
            self.message_user(request, "Only registered merchants or staff can run this action.", messages.ERROR)
            return HttpResponseRedirect("../")
        
        if request.method == 'POST':
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
            form = ImportConfigurationForm(merchant=merchant)

        context = {
            **self.admin_site.each_context(request), 
            'form': form, 
            'merchant': merchant,
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