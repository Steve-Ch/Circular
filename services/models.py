from django.db import models
import uuid
from django.utils.html import format_html
from drf_spectacular.utils import extend_schema_field
from decimal import Decimal
import shortuuid
import os
from django.utils.text import slugify
from nanoid import generate
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.auth.models import AbstractUser
from django.db import models
from accounts.models import User, Estate
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFit




class TimeStamps(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Service(TimeStamps, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)  # e.g., Hairdresser
    description = models.TextField(blank=True)
    # icon = models.ImageField(upload_to="services/", blank=True, null=True)

    def save(self, *args, **kwargs):
        # Format the name field into Title Case before saving
        if self.name:
            self.name = self.name.title()
        super().save(*args, **kwargs)


    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]

    @property
    def image(self):
        # Added a safe check using .first() to prevent AttributeError if no images exist
        first_image_obj = self.images.first()
        if first_image_obj and first_image_obj.image:
            return first_image_obj.image.url
        return None


    def image_preview(self):
        """Displays clickable previews of the first 3 service images in a single row."""
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

    @property
    def service_providers(self):
        return [provider.brand_name for provider in self.providers.all()]


def service_image_path(instance, filename):
    # Separate the extension (e.g., '.jpg') from the original name
    name, ext = os.path.splitext(filename)
    
    # 1. Clean the original name (removes spaces, symbols, uppercase)
    # Example: "Galaxy S21 Ultra" becomes "galaxy-s21-ultra"
    clean_name = slugify(name)
    
    # 2. Generate your 10-character secure random string
    short_id = generate(size=10) 
    
    # 3. Return the compact, beautiful URL path
    return f"services/{clean_name}-{short_id}{ext}"


class ServiceImage(TimeStamps, models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='images')
    image = ProcessedImageField(
        upload_to=service_image_path,
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



class ServiceProvider(TimeStamps, models.Model):
    brand_name = models.CharField(max_length=255, unique=True)
    email = models.EmailField(null=True)
    phone = PhoneNumberField()
    description = models.TextField()
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True, related_name='providers')
    address = models.TextField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.brand_name

class EstateService(TimeStamps, models.Model):
    """Links a service to an estate. Allows admin to toggle availability and set custom fees per estate."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    estate = models.ForeignKey(Estate, on_delete=models.CASCADE, related_name="available_services")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="estate_links")
    request_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_available = models.BooleanField(default=True)  # Admin turns service on/off here
    provider = models.ForeignKey(ServiceProvider, on_delete=models.PROTECT, related_name='estate_services')

    class Meta:
        unique_together = ("estate", "service")
        ordering = ["-created_at"]

    def __str__(self):
        status = "Active" if self.is_available else "Inactive"
        return f"{self.service.name} at {self.estate.name} ({status})"


class ServiceRequest(TimeStamps, models.Model):
    class StatusChoices(models.TextChoices):
        PENDING = "PENDING", "Pending Payment"
        PAID = "PAID", "Fee Paid"
        ACCEPTED = "ACCEPTED", "Accepted by Provider"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resident = models.ForeignKey( User, on_delete=models.CASCADE, related_name="service_requests")
    estate_service = models.ForeignKey(EstateService, on_delete=models.PROTECT, related_name="requests")
    status = models.CharField(max_length=20,choices=StatusChoices.choices,default=StatusChoices.PENDING,)
    fee_paid = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True, null=True)
    transaction = models.OneToOneField(
        'products.Transaction', # Update this path if Transaction is in a different app
        on_delete=models.CASCADE, 
        related_name='service_request',
        null=True, blank=True
    )
    def __str__(self):
        return (
            f"Request #{self.id} - {self.estate_service.service.name} by"
            f" {self.resident.full_name}"
        )

    class Meta:
        ordering = ["-created_at"]

    @property
    def phone(self):
        return self.resident.phone_number

    @property
    def address(self):
        return self.resident.address