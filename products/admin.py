from django.contrib import admin
from .models import (
    Product, Cart,
    CartItem,Order,ProductImage,
    OrderItem, Transaction
    )
# Register your models here.

# admin.site.register(Product)
# admin.site.register(Cart)
# admin.site.register(CartItem)
# admin.site.register(Order)
# admin.site.register(OrderItem)
# admin.site.register(Transaction)



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
    fields = ['product', 'price_at_purchase', 'quantity', 'sub_total']
    readonly_fields = ('product', 'price_at_purchase', 'quantity', 'sub_total')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ('user', 'user__email', 'reference', 'status')
    search_fields = ('user__email','reference')
    readonly_fields = ('user', 'email', 'address', 'reference', 'status')
