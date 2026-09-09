from django.db import models
from products.models import Product, Category
from accounts.models import Estate, User
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import Group
from phonenumber_field.modelfields import PhoneNumberField
import uuid
from django.db.models import Avg
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFit
from django.utils.html import format_html
# Create your models here.

class TimeStamps(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True





class MerchantCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def save(self, *xargs, **kwargs):
            if self.name:
                self.name = self.name.title()
            super().save(*xargs, **kwargs)



    def __str__(self):
        return self.name


class MerchantCategoryExclusionRule(models.Model):
    merchant_category = models.OneToOneField(
        'MerchantCategory', 
        on_delete=models.CASCADE, 
        related_name='exclusion_rule',
        verbose_name="Merchant Category"
    )
    excluded_categories = models.ManyToManyField(
        Category, 
        blank=True,
        verbose_name="Categories to Exclude by Default",
        help_text="Select the product categories that should NOT be imported by default for merchants in this category."
    )

    def __str__(self):
        return f"Default Exclusions for {self.merchant_category.name}"

    class Meta:
        verbose_name = "Category Exclusion Rule"
        verbose_name_plural = "Category Exclusion Rules"



class Merchant(TimeStamps, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store_name = models.CharField(max_length=255, unique=True)
    address = models.TextField(null=True, blank=True)
    phone_number = PhoneNumberField(unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    category = models.ForeignKey(MerchantCategory, on_delete= models.SET_NULL, null=True, blank=True)
    # Store staff users (tied directly to the merchant model)
    staff_users = models.ManyToManyField(User, blank=True, related_name='merchant_staff_profiles')
    brand_logo = ProcessedImageField(
            upload_to= "merchant_logo/",
            processors=[ResizeToFit(1024, 1024)],
            format='JPEG',
            options={'quality': 75},
            blank=True,null=True
        )
    def save(self, *xargs, **kwargs):
        if self.store_name:
            self.store_name = self.store_name.title()
        super().save(*xargs, **kwargs)

    def __str__(self):
        return self.store_name

    def image_preview(self):
            if self.image:
                return format_html('<img src="{}" style="max-height: 200px;" />', self.image.url)
            return "No Image"

    image_preview.short_description = "Image Preview"

    class Meta:
            ordering = ["-created_at"]

    @property
    def estates(self):
        return [estate.name for estate in self.main_estates.all()]

    @property
    def estates_backup(self):
        return [estate.name for estate in self.backup_estates.all()]



class MerchantProduct(TimeStamps, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='inventory')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Select Product from Catalog", help_text="select a product here")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    display = models.BooleanField(default=True,)


    @property
    # @extend_schema_field(Decimal)
    def name(self):
        return self.product.name

    @property
    def image_preview(self):
        return self.product.image_preview

    @property
    def average_rating(self):
        """Calculates the average rating from related reviews."""
        # Use the 'reviews' related_name you defined on your Review model
        result = self.reviews.aggregate(Avg('rating'))['rating__avg']
        
        # Round the result to 1 decimal place, or return 0 if there are no reviews
        return round(result, 1) if result is not None else 0.0

        
    class Meta:
        unique_together = ('merchant', 'product')
        verbose_name = "My Product Inventory"
        verbose_name_plural = "My Product Inventory"
        ordering = ["-created_at"]

        
    def clean(self):
        super().clean()
        # Enforce rule: No price means display MUST be False
        if self.price is None and self.display:
            raise ValidationError({
                'display': "You cannot set a product to display until you have assigned a valid price to it."
            })

    def save(self, *args, **kwargs):
        # Double-check constraint logic before writing to DB
        if self.price is None:
            self.display = False
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name}"