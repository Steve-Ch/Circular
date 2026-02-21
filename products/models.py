from django.db import models
from accounts.models import User
import uuid
from django.db.models import Sum
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFit
# Create your models here.


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
    quantity = models.PositiveIntegerField(default=1)

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

class Cart(TimeStamps, models.Model):
    user= models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')

    @property
    def price_total(self):
        return self.items.aggregate(total=Sum('price'))['total'] or 0
    
    def __str__(self):
        return f"{self.user.email} | ₦{self.price_total}"
        



class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)    
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    
    @property
    def price(self):
        return self.product.price
    

    def __str__(self):
        return f"{self.product.name}"




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
    reference = models.CharField(max_length=15)
    status = models.CharField(max_length=20,choices=Status.choices, default=Status.PENDING)
    full_name = models.CharField(max_length=30)
    email = models.EmailField()

    def __str__(self):
        return f"{self.user.email} | {self.full_name}"

    @property
    def price_total(self):
        return self.items.aggregate(total=Sum('price_at_purchase'))['total'] or 0

    class Meta:
        ordering = ["-created_at"]



class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"