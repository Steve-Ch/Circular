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






class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=30)
    description = models.TextField()
    categories = models.ManyToManyField(Category, related_name='projects', blank=False)
    price = models.DecimalField(decimal_places=2,max_digits=10)
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(999)
        ]
    )
    


    @property
    def image(self):
        # Added a safe check using .first() to prevent AttributeError if no images exist
        first_image_obj = self.images.first()
        if first_image_obj and first_image_obj.image:
            return first_image_obj.image.url
        return None


    def image_preview(self):
        """Displays the preview of the first product image in the admin panel."""
        first_image_obj = self.images.first()
        if first_image_obj and first_image_obj.image:
            return format_html('<img src="{}" style="max-height: 100px; border-radius: 5px;" />', first_image_obj.image.url)
        return "No Image"


    # @extend_schema_field(Decimal)
    def categories_display(self):
        return [cat.name for cat in self.categories.all()]
    categories_display.short_description = "Categories"

    # @property
    # def average_rating(self):
    #     return self.reviews.aggregate(Avg('rating'))['rating__avg'] or 0


    def __str__(self):
        return f"{self.name}"



def product_image_path(instance, filename):
    # 1. Safe fallback to prevent crashes if product is not linked yet
    if instance and getattr(instance, 'product', None) and instance.product.name:
        product_name = instance.product.name
    else:
        product_name = "unassigned"

    # 2. Strip spaces and special characters for a clean filesystem name
    clean_name = "".join([c for c in product_name if c.isalnum()]).lower()
    random_name = uuid.uuid4()
    
    # 3. Flattens path to avoid Windows directory creation collisions (FileExistsError)
    return f'product-images/{clean_name}-{random_name}.jpg'



class ProductImage(models.Model):
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
    
    reference = models.CharField(max_length=15, unique=True)
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
    user= models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')

    
    @property
    @extend_schema_field(Decimal)
    def price_total(self):
        return self.items.aggregate(
            total=Sum(F('quantity') * F('product__price'))
        )['total'] or 0
    
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
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user =  models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    address = models.CharField(max_length=50)
    estate = models.ForeignKey(Estate, on_delete=models.CASCADE, related_name='orders', null=True, blank=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='orders', null=True, blank=True)
    status = models.CharField(max_length=20,choices=Status.choices, default=Status.PENDING)
    full_name = models.CharField(max_length=30)
    email = models.EmailField()

    def __str__(self):
        return f"{self.user.email} | {self.full_name}"
    
    
    @property
    @extend_schema_field(Decimal)
    def price_total(self):
        return self.items.aggregate(total=Sum('price_at_purchase'))['total'] or 0
    
    def phone_number(self):
        return self.user.phone_number


    class Meta:
        ordering = ["-created_at"]



class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(999)
        ]
    )
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    @property
    def sub_total(self):
        # Check if price_at_purchase exists before multiplying
        if self.price_at_purchase is not None:
            return self.price_at_purchase * self.quantity
        return 0
    
    @property
    def image(self):
        return self.product.image_preview
