from django.contrib import admin
from .models import (
    Service, EstateService, 
    ServiceProvider, ServiceRequest, 
    ServiceImage
    )



# def get_user_provider(user):
#     """
#     returns seervice provider
#     """
#     if user.is_superuser:
#         return None
#     # if hasattr(user, 'merchant_profile'):
#     #     return user.merchant_profile
#     return user.merchant_staff_profiles.first()


# Register your models here.
class ServiceImageInline(admin.StackedInline):
    model = ServiceImage
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


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    inlines = [ServiceImageInline]
    list_display = ('name', 'service_providers')
    # list_filter = (,)
    search_fields = ('name',)
    # readonly_fields = ('service_providers',)



    # def get_queryset(self, request):
    #     qs = super().get_queryset(request)
    #     if request.user.is_superuser:
    #         return qs
            
    #     provider = get_user_merchant(request.user)
    #     if merchant:
    #         return qs.filter(merchant=merchant)
            
    #     return qs.none()


@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    # inlines = []
    list_display = ('brand_name', 'email', 'service', 'phone',  'address')
    # list_filter = (,)
    search_fields = ('brand_name',)
    # readonly_fields = ('providers',)



@admin.register(EstateService)
class EstateServiceAdmin(admin.ModelAdmin):
    fields = ('estate','service','provider','request_fee','is_available',)


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    # inlines = []
    list_display = ('resident', 'estate_service', 'status',  'phone', 'address')
    list_filter = ('status',)
    # search_fields = ('brand_name',)
    fields = ('resident','estate_service','status','fee_paid','notes',)
    readonly_fields = ('resident','estate_service','status','fee_paid','notes',)