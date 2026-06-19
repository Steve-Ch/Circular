from django.contrib import admin
from .models import DeliveryTier, SiteConfiguration
from solo.admin import SingletonModelAdmin  
# Register your models here.


class DeliveryTierInline(admin.TabularInline):
    model = DeliveryTier
    extra = 1 # Shows one empty row by default to add new tiers

@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(SingletonModelAdmin):
    inlines = [DeliveryTierInline]