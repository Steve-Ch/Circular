from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Estate
from django.utils.html import format_html
from django.contrib.admin.models import LogEntry
from services.models import EstateService
import pandas as pd
from django.urls import path
from django.http import HttpResponse



@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'action_time', 'content_type', 'object_repr', 'action_flag', 'change_message', 'view_object_link')
    list_filter = ('user', 'content_type', 'action_flag')
    search_fields = ('object_repr', 'change_message')
    change_list_template = "admin/user_change_list.html"

    def view_object_link(self, obj):
        if obj.action_flag == 3:  # Deletion
            return "(deleted)"
        return format_html('<a href="{}">View</a>', obj.get_admin_url())
    
    view_object_link.short_description = "View Object"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            # Added a highly specific name to avoid global admin routing conflicts
            path('download-csv/', self.admin_site.admin_view(self.download_users_csv), name='systeme_user_csv_export'),
        ]
        return custom_urls + urls

    def download_users_csv(self, request):
        # 1. Explicitly use 'User.objects' instead of 'self.model' to prevent context mixups
        # 2. Use .values() to fetch ONLY the required fields, making the DB query extremely fast
        users_qs = User.objects.exclude(first_name="", last_name="").values(
            'first_name', 'last_name', 'email', 'phone_number'
        )

        # 3. Load directly into a Pandas DataFrame
        df = pd.DataFrame.from_records(users_qs)

        # 4. Rename columns to match Systeme.io strict headers
        if not df.empty:
            df.rename(columns={
                'first_name': 'First Name',
                'last_name': 'Last Name',
                'email': 'Email',
                'phone_number': 'Phone Number'
            }, inplace=True)
        else:
            # Fallback to empty DataFrame with correct headers if no users match
            df = pd.DataFrame(columns=['First Name', 'Last Name', 'Email', 'Phone Number'])

        # 5. Create HTTP Response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="systeme_io_contacts.csv"'
        
        # 6. Write DataFrame to CSV directly into the response (index=False removes row numbers)
        df.to_csv(response, index=False)

        return response



# 1. Create an inline using the auto-generated intermediate table
# class MerchantEstateInline(admin.TabularInline):
#     # This targets the hidden 'through' table connecting both models
#     model = Merchant.estate.through 
#     extra = 1
    
#     # 2. Use autocomplete_fields to easily search existing merchants
#     autocomplete_fields = ['merchant'] 


class ServiceImageInline(admin.StackedInline):
    model = EstateService
    extra = 0
    



# admin.site.register(User)
@admin.register(Estate)
class EstateAdmin(admin.ModelAdmin):
    list_display = ( 'name', 'town', 'state',)
    search_fields = ('name',)
    list_filter = ('state','town')
    ordering = ['state', 'town', 'name']
    readonly_fields = ('image_preview',)
    inlines = [ServiceImageInline]

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    ordering = ('date_joined',)
    list_display = ( 'email', 'full_name', 'phone_number', 'is_active', 'is_staff', 'date_joined', 'all_groups')
    search_fields = ('email',)

    # This tells Django to use the email field as the main link, instead of the missing username field
    list_display_links = ('email',)

    # 1. Fixed Fieldsets (for editing existing users)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'phone_number', 'estate', 'address', 'eligible_for_free_delivery')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'phone_number', 'is_staff', 'is_superuser'),
        }),
        
    )




    def get_readonly_fields(self, request, obj=None):
            if obj:
                readonly = super().get_readonly_fields(request, obj) + ('email','phone_number','last_login', 'date_joined','first_name', 'last_name', 'estate', 'address')
                if not request.user.is_superuser:
                    readonly = readonly + ('is_superuser','is_staff','groups', 'user_permissions','groups')
                return readonly
            else:
                  return ()

