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
    categories = models.ManyToManyField(Category, related_name='projects', blank=False)
    price = models.DecimalField(decimal_places=2,max_digits=10)
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(999)
        ]
    )


    # @extend_schema_field(Decimal)
    def categories_display(self):
        return [cat.name for cat in self.categories.all()]
    categories_display.short_description = "Categories"

    def __str__(self):
        return f"{self.name}"



def product_image_path(instance, filename):
    product =instance.product
    return f'product images/{product.name}'

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
        PAID = "PAID", "Paid"
        SHIPPED = "SHIPPED", "Shipped"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user =  models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    address = models.CharField(max_length=50)
    reference = models.CharField(max_length=15,unique=True)
    status = models.CharField(max_length=20,choices=Status.choices, default=Status.PENDING)
    full_name = models.CharField(max_length=30)
    email = models.EmailField()

    def __str__(self):
        return f"{self.user.email} | {self.full_name}"
    
    
    @property
    @extend_schema_field(Decimal)
    def price_total(self):
        return self.items.aggregate(total=Sum('price_at_purchase'))['total'] or 0

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
                        self.reference = shortuuid.ShortUUID().random(length=15)
                        super().save(*args, **kwargs)
                    break
                except IntegrityError:
                    continue
        else:
            super().save(*args, **kwargs)