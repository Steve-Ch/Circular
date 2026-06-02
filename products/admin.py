from django.contrib import admin,messages
from django.urls import path, reverse
from .models import (
    Product, Cart,Review,
    CartItem,Order,ProductImage,
    OrderItem, Transaction, Category
    )
from django.shortcuts import render, redirect, get_object_or_404
from accounts.utils import generate_otp, validate_otp,send_html_mail
from django.utils import timezone
from datetime import timedelta

# Register your models here.

# admin.site.register(Product)
# admin.site.register(Cart)
# admin.site.register(CartItem)
admin.site.register(Review)
# admin.site.register(OrderItem)
# admin.site.register(Transaction)
admin.site.register(Category)


# @admin.register(LogEntry)
# class LogEntryAdmin(admin.ModelAdmin):
#     list_display = ('user', 'action_time', 'content_type', 'object_repr', 'action_flag', 'change_message', 'view_object_link')
#     list_filter = ('user', 'content_type', 'action_flag')
#     search_fields = ('object_repr', 'change_message')

#     def view_object_link(self, obj):
#         if obj.action_flag == 3:  # Deletion
#             return "(deleted)"
#         return format_html('<a href="{}">View</a>', obj.get_admin_url())
    
#     view_object_link.short_description = "View Object"


class ProductImageInline(admin.StackedInline):
    model = ProductImage
    extra = 1
    fields = ['image_preview', 'image',]
    readonly_fields = ('image_preview',)
    

    # def get_fields(self, request, obj=None):
    #     if obj:  # editing existing object
    #         return (
    #             'page', 'title','subtitle', 'description','image', 'image_preview', 
    #         )
    #     else:  # adding new object
    #         return ('page','title','subtitle','description','image', 'image_preview', )

    # def get_readonly_fields(self, request, obj=None):
    #     if obj:  # Editing an existing object
    #         return (
    #             'image_preview',
    #         )
    #     else:  # Adding a new object
    #             return ('image_preview',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline]
    list_display = ('name', 'categories_display', 'quantity', 'price', )
    list_filter = ('categories',)
    search_fields = ('name',)



class CartItemInline(admin.StackedInline):
    model = CartItem
    extra = 0  # Set this to 0 to remove empty placeholder rows
    fields = ['product', 'price', 'quantity', 'sub_total']
    readonly_fields = ('product', 'price', 'quantity', 'sub_total')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    inlines = [CartItemInline]
    list_display = ('user', 'user__email', )
    search_fields = ('user__email',)
    readonly_fields = ('user', )





class OrderItemInline(admin.StackedInline):
    model = OrderItem
    extra = 0  # Set this to 0 to remove empty placeholder rows
    fields = ['product', 'price_at_purchase', 'quantity', 'sub_total', 'image']
    readonly_fields = ('product', 'price_at_purchase', 'quantity', 'sub_total', 'image')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False





@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ('user', 'email', 'phone_number', 'transaction', 'status', 'price_total', 'created_at')
    search_fields = ('email','reference')
    list_filter = ('estate','status')
    fields = ['user', 'estate', 'address', 'transaction', 'status','phone_number', 'created_at','price_total',]
    readonly_fields = ('full_name','user', 'email', 'phone_number', 'estate', 'address', 'transaction', 'created_at','price_total',)


    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if object_id:
            # Dynamically applies template for the edit page
            self.change_form_template = 'admin/products/order_changeform.html'
        else:
            self.change_form_template = None
            
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<uuid:pk>/send-otp/',
                self.admin_site.admin_view(self.confirm_delivery),
                name='confirm_delivery'
            ),
            
        ]
        return custom + urls

    def confirm_delivery(self, request, pk):
        # Import the correct ValidationError thrown by your utils file
        from rest_framework.exceptions import ValidationError
        
        order = get_object_or_404(Order, pk=pk)
        user = order.user

        if request.method == 'POST':
            submitted_code = request.POST.get('otp')

            
            try:
                # Wrap the validation function inside the try block to catch its failure exceptions
                if user.otp == submitted_code:

                    if timezone.now() - user.otp_expiry > timedelta(minutes=15):
                        raise ValidationError("OTP has expired.")

                    # Invalidate OTP after successful use
                    user.otp = None
                    user.otp_expiry = None
                    user.save(update_fields=["otp", "otp_expiry"])
                    order.status = Order.Status.DELIVERED
                    order.save()
                    messages.success(request, "Order Status Updated to Delivered")
                else:
                    messages.error(request, "Invalid OTP code supplied.")
                    
            except ValidationError as ve:
                # Catch the specific REST Framework ValidationError raised by your utils file
                messages.error(request, f" {ve.detail[0] if isinstance(ve.detail, list) else ve.detail}")
            except Exception as e:
                # Catch general database or unexpected runtime errors
                messages.error(request, f"Unexpected error: {e}")

            return redirect(reverse('admin:products_order_change', args=[pk]))

        # --- GET request logic for the "Send OTP" button ---
        otp = generate_otp()
        user.otp = otp
        user.otp_expiry = timezone.now() + timezone.timedelta(minutes=15)
        user.save()

        subject = "Delivery Confimation Mail"
        message = f"""Hello {user.full_name}, please use the 6-digit code to validate your delivery with the driver, Thanks"""
        send_html_mail(user.email,subject,message, otp=otp)
        messages.success(request, "✅ OTP sent successfully.")
        return redirect(reverse('admin:products_order_change', args=[pk]))



