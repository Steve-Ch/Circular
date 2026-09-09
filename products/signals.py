from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product, CartItem
from merchant.models import MerchantProduct

# 1. Listen for global product display toggles by SuperAdmins
@receiver(post_save, sender=Product)
def remove_hidden_products_from_carts(sender, instance, **kwargs):
    if not instance.display:
        # Deletes all cart items globally that contain this base product
        CartItem.objects.filter(merchant_product__product=instance).delete()

# 2. Listen for merchant-level product display toggles
@receiver(post_save, sender=MerchantProduct)
def remove_hidden_merchant_products_from_carts(sender, instance, **kwargs):
    if not instance.display:
        # Deletes only cart items linked to this specific merchant's listing
        CartItem.objects.filter(merchant_product=instance).delete()