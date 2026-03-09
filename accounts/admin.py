from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User

# admin.site.register(User)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    ordering = ('email',)
    list_display = ('full_name', 'email', 'phone_number', 'is_active', 'is_staff')
    search_fields = ('email',)
    # readonly_fields = (
    #     'first_name', 'last_name', 'phone_number', 
    #     'address', 'is_active', 'is_staff', 'is_superuser', 
    #     'groups', 'user_permissions','last_login', 'date_joined'
    #     ) 
    # This tells Django to use the email field as the main link
    # instead of the missing username field
    list_display_links = ('email',)

    # 1. Fixed Fieldsets (for editing existing users)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'phone_number', 'address')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    # 2. Fixed Add Fieldsets (for creating new users)
    # add_fieldsets = (
    #     (None, {
    #         'classes': ('wide',),
    #         'fields': ('email', 'password', 'phone_number', 'is_staff', 'is_superuser'),
    #     }),
    # )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'phone_number', 'is_staff', 'is_superuser'),
        }),
        
    )




    def get_readonly_fields(self, request, obj=None):
            if obj:
                readonly = super().get_readonly_fields(request, obj) + ('email','phone_number','last_login', 'date_joined','first_name', 'last_name', 'address')
                if not request.user.is_superuser:
                    readonly = readonly + ('is_superuser','is_staff','groups', 'user_permissions','groups')
                return readonly
            else:
                  return ()


# def get_readonly_fields(self, request, obj=None):
#         if obj:  # Editing an existing object
#             return (
#                 'requirement','file','value','reviewed_at','reviewed_by',
#             )
#         else:  # Adding a new object
#                 return ()