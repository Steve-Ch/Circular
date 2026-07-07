from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from django.core.validators import MinLengthValidator,MaxLengthValidator
import uuid
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFit
from django.utils.html import format_html
from django.core.exceptions import ValidationError 
# Create your models here.


class Estate(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address = models.TextField()
    state = models.CharField(max_length=100)
    town = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    image = ProcessedImageField(
        upload_to='estates',
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
        return self.name
    
    def clean(self):
        # 1. Standardize the name to Title Case for validation
        if self.name:
            titled_name = self.name.title()
            
            # 2. Check if this title-cased name already exists (excluding the current record if editing)
            queryset = Estate.objects.filter(name=titled_name)
            if self.pk:
                queryset = queryset.exclude(pk=self.pk)
                
            if queryset.exists():
                raise ValidationError({'name': f"An estate named '{titled_name}' already exists."})

    def save(self, *args, **kwargs):
        # Run the clean method validation manually in case save() is called outside the admin panel
        self.full_clean() 
        
        self.name = self.name.title()
        self.state = self.state.title()
        self.town = self.town.title()
        
        super().save(*args, **kwargs)
    



class TimeStamps(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    phone_number = PhoneNumberField(unique=True, null=False, blank=False)
    avatar = ProcessedImageField(
            upload_to='avatars/',
            processors=[ResizeToFit(1024, 1024)],
            format='JPEG',
            options={'quality': 75},
            blank=True,null=True
        )    
    is_active = models.BooleanField(default=False)
    is_rider = models.BooleanField(default=False)
    pin=models.CharField(max_length=5,validators=[MinLengthValidator(5),MaxLengthValidator(5)],default=00000)
    otp = models.CharField(max_length=6,null=True,blank=True)
    otp_expiry = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)
    address = models.CharField(max_length=120, blank=True, null=True)
    estate = models.ForeignKey(Estate, blank = True, null=True, on_delete=models.CASCADE)


    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.full_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    

# class Address(TimeStamps, models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
#     address = models.CharField(max_length=50)

#     class Meta:
#         verbose_name_plural = "Addresses"


