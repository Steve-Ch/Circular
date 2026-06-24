from django.contrib import admin,messages
from django.urls import path, reverse
from .models import (
    Product, Cart,Review,
    CartItem,Order,ProductImage, RefundRequest,
    OrderItem, Transaction, Category
    )
import requests
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from accounts.utils import generate_otp, validate_otp,send_html_mail
from django.utils import timezone
from datetime import timedelta
from django.utils.html import format_html
# Register your models here.

admin.site.register(Review)
admin.site.register(Category)
# admin.site.register(Transaction)


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
    list_display = ('name', 'categories_display', 'display', 'price','created_at', )
    list_filter = ('categories',)
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')

    
    def get_fields(self, request, obj=None):
        if obj:  # editing existing object
            return (
                'name', 'description', 'categories', 'price',
                'display', 'created_at', 'updated_at',
            )
            
        else:  # adding new object
            return (
                'name', 'description', 'categories', 'price',
                'display',
            )




class CartItemInline(admin.StackedInline):
    model = CartItem
    extra = 0  # Set this to 0 to remove empty placeholder rows
    fields = ['product', 'quantity','price','sub_total', 'image_preview']
    readonly_fields = ('product', 'price', 'quantity', 'price','sub_total', 'image_preview')

    def has_add_permission(self, request, obj=None):
        return False

    # def has_delete_permission(self, request, obj=None):
    #     return False

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
    # list_display = ('user', 'email', 'phone_number', 'estate', 'status_with_emoji', 'price_total', 'created_at')
    list_display = ('user', 'price_total','status','phone_number', 'email',  'estate', 'created_at')
    search_fields = ('full_name', 'items__product__name')
    list_filter = ('estate','status')
    fields = ['user', 'estate', 'address', 'transaction', 'status','phone_number', 'created_at','price_total','rider']
    readonly_fields = ('full_name','user', 'email', 'phone_number', 'estate', 'address', 'transaction', 'created_at','price_total', 'rider')

 # 2. Created the custom list display method
    # def status_with_emoji(self, obj):
    #     status_mapping = {
    #         "PENDING": "⏳ Pending",
    #         "IN PROGRESS": "🏍️ In Progress",
    #         "DELIVERED": "✅ Delivered",
    #         "CANCELLED": "❌ Cancelled",
    #     }
    #     # Looks up the current status or falls back to raw status text
    #     return format_html(status_mapping.get(obj.status, obj.status))
    
    # # 3. Formatted column headers and enabled database sorting
    # status_with_emoji.short_description = 'Status'
    # status_with_emoji.admin_order_field = 'status'


    # 1. Register the action locally within this ModelAdmin
    actions = ['Accept_Orders']

    # 2. Define the action as a method (notice the 'self' argument)
    @admin.action(description="Accept selected Orders")
    def Accept_Orders(self, request, queryset):
        # 3. Restrict execution to the "Rider" group
        if not request.user.groups.filter(name='Rider').exists():
            self.message_user(
                request, 
                "Error: Only members of the 'Rider' group can perform this action.", 
                level=messages.ERROR
            )
            return

        # 4. Perform the logic
# 2. Get the total number of items the user selected
        total_selected = queryset.count()

        # 3. Filter the queryset to only include "pending" items
        pending_items = queryset.filter(status=Order.Status.PENDING)
        
        # 4. Update only the filtered pending items
        updated_count = pending_items.update(status=Order.Status.IN_PROGRESS, rider=request.user.email)
        
        # 5. Calculate how many items were ignored
        ignored_count = total_selected - updated_count

        # 6. Send the breakdown message to the user
        message = f"Successfully updated {updated_count} order(s) to 'In Progress'."
        if ignored_count > 0:
            message += f" Ignored {ignored_count} order(s) because they were not 'Pending'."
            
        self.message_user(request, message, level=messages.SUCCESS)        
        



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

            path(
                '<uuid:pk>/accept-order/',
                self.admin_site.admin_view(self.begin_delivery),
                name='accept_order'
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
        messages.success(request, "OTP sent successfully.")
        return redirect(reverse('admin:products_order_change', args=[pk]))





    def begin_delivery(self, request, pk):
        
        order = get_object_or_404(Order, pk=pk)
        user = order.user
        if order.status == Order.Status.PENDING:
            order.status = Order.Status.IN_PROGRESS
            order.rider = request.user.email
            order.save()

            subject = "Delivery In Progress"
            message = f"""Hello {user.full_name}, your item delivery is in progress. the rider would reach out to you soon for pickup"""
            send_html_mail(user.email,subject,message)

            messages.success(request, "Order Accepted Successfully.")
            return redirect(reverse('admin:products_order_changelist'))
        
        
            
        else:
            messages.error(request, "Only pending orders can be accepted")
            return redirect(reverse('admin:products_order_change', args=[pk]))
            






@admin.register(RefundRequest)
class RefundrequestAdmin(admin.ModelAdmin):
    list_display = ('order__full_name','status','cancellation_reason','created_at')
    search_fields = ('order__full_name',)
    list_filter = ('status',)
    fields = ['order', 'cancellation_reason', 'cancellation_note', 'status', 'paystack_reference']
    readonly_fields = ('order', 'cancellation_reason', 'cancellation_note', 'status', 'paystack_reference')



    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if object_id:
            # Dynamically applies template for the edit page
            self.change_form_template = 'admin/products/refund_request_change.html'
        else:
            self.change_form_template = None
            
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<uuid:pk>/refund-user/',
                self.admin_site.admin_view(self.trigger_paystack_refund),
                name='process_refund'
            ),
            
        ]
        return custom + urls




    def trigger_paystack_refund(self, request, pk):
        refund_obj = get_object_or_404(RefundRequest, pk=pk)
        reference = refund_obj.order.transaction.reference
        
        # Use get_cancellation_reason_display() to show "Bought by mistake" instead of "MISTAKE"
        reason = refund_obj.get_cancellation_reason_display() 
        
        # FIXED: Added the 'api.' subdomain
        url = "https://api.paystack.co/refund" 
        
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "transaction": reference,
            "customer_note": f"Cancellation due to: {reason}"
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response_data = response.json()

            if response.status_code != 200 or not response_data.get("status"):
                # Pull the exact error message from Paystack if it fails
                error_msg = response_data.get("message", "Paystack refund error.")
                messages.error(request, f"Refund failed: {error_msg}")
                return redirect(reverse('admin:products_refundrequest_change', args=[pk]))

            # Update the local DB status to reflect the successful payout request
            refund_obj.status = refund_obj.STATUS_CHOICES.REFUNDED
            refund_obj.save()

            messages.success(request, f"Paystack refund request made successfully: {response_data.get('message')}")
            return redirect(reverse('admin:products_refundrequest_change', args=[pk]))
            
        except requests.RequestException as e:
            messages.error(request, f"Request failed: {e}")
            return redirect(reverse('admin:products_refundrequest_change', args=[pk]))









