from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils import timezone
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from django.core.validators import MinLengthValidator,MaxLengthValidator
import uuid
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFit

# Create your models here.




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
    pin=models.CharField(max_length=5,validators=[MinLengthValidator(5),MaxLengthValidator(5)],default=00000)
    otp = models.CharField(max_length=6,null=True,blank=True)
    otp_expiry = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)
    address = models.CharField(max_length=30, blank=True, null=True)


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