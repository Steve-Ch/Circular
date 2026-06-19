from django.db import models
from accounts.models import User
import uuid
from django.db.models import Sum, F
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFit
from django.utils.html import format_html
from drf_spectacular.utils import extend_schema_field
from decimal import Decimal
import shortuuid
from django.db import IntegrityError, transaction
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Avg
from accounts.models import Estate
import os
from django.utils.text import slugify
from nanoid import generate
from website.models import SiteConfiguration, DeliveryTier




class TimeStamps(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True



class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"






class Product(TimeStamps, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=30)
    description = models.TextField()
    categories = models.ManyToManyField(Category, related_name='projects', blank=False)
    price = models.DecimalField(decimal_places=2,max_digits=10)
    display = models.BooleanField(default=True,)


    def save(self, *args, **kwargs):
        # 1. Check if this is an update to an existing product
        if self.pk:
            old_instance = Product.objects.filter(pk=self.pk).first()
            
            # 2. Trigger deletion only if 'display' was True and is changing to False
            if old_instance and old_instance.display and not self.display:
                # Efficiently bulk delete matching items from all user carts
                CartItem.objects.filter(product=self).delete()

        # 3. Proceed with the normal save operation
        super().save(*args, **kwargs)
    


    @property
    def image(self):
        # Added a safe check using .first() to prevent AttributeError if no images exist
        first_image_obj = self.images.first()
        if first_image_obj and first_image_obj.image:
            return first_image_obj.image.url
        return None


    def image_preview(self):
        """Displays clickable previews of the first 3 product images in a single row."""
        # 1. Fetch up to the first 3 image objects efficiently
        image_objs = self.images.all()[:3]
        
        if not image_objs:
            return "No Image"

        html_elements = []
        
        for obj in image_objs:
            if obj.image:
                # 2. Wrap each image in an <a> tag targeting a new tab (_blank)
                html_elements.append(
                    format_html(
                        '<a href="{0}" target="_blank" style="margin-right: 8px; display: inline-block;">'
                        '<img src="{0}" style="max-height: 100px; border-radius: 5px; border: 1px solid #ddd;" />'
                        '</a>',
                        obj.image.url
                    )
                )

        # 3. Join all HTML blocks together into a single string row
        if html_elements:
            return format_html("".join(html_elements))
        
        return "No Image"


    def categories_display(self):
        return [cat.name for cat in self.categories.all()]
    categories_display.short_description = "Categories"

    @property
    def average_rating(self):
        """Calculates the average rating from related reviews."""
        # Use the 'reviews' related_name you defined on your Review model
        result = self.reviews.aggregate(Avg('rating'))['rating__avg']
        
        # Round the result to 1 decimal place, or return 0 if there are no reviews
        return round(result, 1) if result is not None else 0.0


    def __str__(self):
        return f"{self.name}"
    
    class Meta:
        ordering = ["-created_at"]




def product_image_path(instance, filename):
    # Separate the extension (e.g., '.jpg') from the original name
    name, ext = os.path.splitext(filename)
    
    # 1. Clean the original name (removes spaces, symbols, uppercase)
    # Example: "Galaxy S21 Ultra" becomes "galaxy-s21-ultra"
    clean_name = slugify(name)
    
    # 2. Generate your 10-character secure random string
    short_id = generate(size=10) 
    
    # 3. Return the compact, beautiful URL path
    return f"product-images/{clean_name}-{short_id}{ext}"


class ProductImage(TimeStamps, models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = ProcessedImageField(
        upload_to=product_image_path,
        processors=[ResizeToFit(1024, 1024)],
        format='JPEG',
        options={'quality': 75},
        blank=True,null=True
    )

    def image_preview(self):
        if self.image:
            return format_html('<img src="{}" style="max-height: 200px;" />', self.image.url)
        return "No Image"

    image_preview.short_description = "Image Preview"


    def __str__(self):
        return f"{self.image.name}"

    class Meta:
        ordering = ["-created_at"]

class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevents multiple reviews from the same user for one product
        unique_together = ('product', 'user') 
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.rating}*)"





class Transaction(TimeStamps, models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESSFUL = "SUCCESSFUL", "Successful"
        FAILED = "FAILED", "Failed"
    
    reference = models.CharField(max_length=20, unique=True)
    user = models.ForeignKey(User, related_name='transactions', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20,choices=Status.choices, default=Status.PENDING)


    def save(self, *args, **kwargs):
        if not self.reference: 
            while True:
                try:
                    with transaction.atomic():
                        self.reference = shortuuid.ShortUUID().random(length=20)
                        super().save(*args, **kwargs)
                    break
                except IntegrityError:
                    continue
        else:
            super().save(*args, **kwargs)
    
    def __str__(self):
        return self.reference
 



class Cart(TimeStamps, models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')

    @property
    @extend_schema_field(Decimal)
    def subtotal(self):
        """Calculates total price of all items in the cart (excluding delivery)."""
        return self.items.aggregate(
            total=Sum(F('quantity') * F('product__price'))
        )['total'] or Decimal('0.00')

    @property
    @extend_schema_field(Decimal)
    def delivery_fee(self):
        """Calculates the dynamic delivery fee based on the current subtotal."""
        # Import inside the method if needed to prevent circular imports
        from website.models import SiteConfiguration, DeliveryTier 
        
        order_total = self.subtotal
        config = SiteConfiguration.get_solo()
        
        # Get the highest applicable tier matching the current subtotal
        matching_tier = DeliveryTier.objects.filter(
            min_order_value__lte=order_total
        ).order_by('-min_order_value').first()
        
        if matching_tier:
            return matching_tier.delivery_fee
            
        return config.default_delivery_fee

    @property
    @extend_schema_field(Decimal)
    def price_total(self):
        """Calculates the final grand total (items + delivery fee)."""
        return self.subtotal + self.delivery_fee

    def __str__(self):
        return f"{self.user.email}"





class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)    
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(999)
        ]
    )

    # @extend_schema_field(Decimal)
    @property
    def image(self):
        return self.product.images.first().image.url
    
    @property
    def image_preview(self):
        return self.product.image_preview
    
    

    @property
    @extend_schema_field(Decimal)
    def price(self):
        return self.product.price
    
    @property
    @extend_schema_field(Decimal)
    def sub_total(self):
        return self.quantity * self.product.price

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"




class Order(TimeStamps, models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_PROGRESS = "IN PROGRESS", "In Progress"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user =  models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    address = models.CharField(max_length=50)
    estate = models.ForeignKey(Estate, on_delete=models.SET_NULL, related_name='orders', null=True, blank=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, related_name='orders', null=True, blank=True)
    status = models.CharField(max_length=20,choices=Status.choices, default=Status.PENDING)
    full_name = models.CharField(max_length=30)
    email = models.EmailField()
    rider = models.CharField(max_length=25, null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} | {self.full_name}"
    
    
    @property
    @extend_schema_field(Decimal)
    def price_total(self):
        # Multiply price by quantity for each item, then sum them together
        return self.items.aggregate(
            total=Sum(F('price_at_purchase') * F('quantity'))
        )['total'] or 0
    def phone_number(self):
        return self.user.phone_number
    def reference(self):
        return self.transaction.reference if self.transaction else None


    class Meta:
        ordering = ["-created_at"]



class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    # 1. Allow the link to be NULL when product is deleted
    product = models.ForeignKey('Product', on_delete=models.SET_NULL, null=True, blank=True)

    product_name = models.CharField(max_length=255, null=True, blank=True)
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(999)
        ]
    )
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    @property
    def sub_total(self):
        # Check if price_at_purchase exists before multiplying
        if self.price_at_purchase is not None:
            return self.price_at_purchase * self.quantity
        return 0
    
    @property
    def image(self):
        return self.product.image_preview if self.product else None


class RefundRequest(TimeStamps, models.Model):

    class CANCELLATION_REASONS(models.TextChoices):
        MISTAKE = 'MISTAKE', 'Bought by mistake'
        DELAY = 'DELAY', 'Delivery time is too long'
        PRICE = 'PRICE', 'Found a better price elsewhere'
        OTHER = 'OTHER', 'Other reasons'

    class STATUS_CHOICES(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        REFUNDED = 'REFUNDED', 'Refunded'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CHOICES.PENDING)
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    paystack_reference = models.CharField(max_length=100, null=True, blank=True)
    cancellation_reason = models.CharField(max_length=20, choices=CANCELLATION_REASONS.choices, default=CANCELLATION_REASONS.OTHER)
    cancellation_note = models.TextField(null=True, blank=True)