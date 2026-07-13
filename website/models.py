from django.db import models
from solo.models import SingletonModel
from datetime import time



class SiteConfiguration(SingletonModel):
    default_delivery_fee = models.DecimalField(
        decimal_places=2, 
        max_digits=10, 
        default=500.00,
        help_text="Fee used if order total is below the first tier threshold."
    )
    minimum_tx = models.DecimalField(
        decimal_places=2, 
        max_digits=10,
        default=2500,
        help_text="Minimum amount for transaction, no order can be placed with amount less than this value."
    )
    closing_hour = models.TimeField(default=time(20, 0))
    test_mode = models.BooleanField(
        default=False,
        help_text="Turning this on defaults to test paystack keys."
        )


    def __str__(self):
        return "Site Configuration"

class DeliveryTier(models.Model):
    # We use a ForeignKey to link it directly to your configuration
    site_config = models.ForeignKey(
        SiteConfiguration, 
        on_delete=models.CASCADE, 
        related_name='delivery_tiers'
    )
    min_order_value = models.DecimalField(
        decimal_places=2, 
        max_digits=10,
        help_text="The minimum order total to trigger this fee."
    )
    delivery_fee = models.DecimalField(
        decimal_places=2, 
        max_digits=10
    )

    class Meta:
        ordering = ['min_order_value'] # Keeps tiers sorted lowest to highest

    def __str__(self):
        return f"Orders over {self.min_order_value} = Fee: {self.delivery_fee}"


