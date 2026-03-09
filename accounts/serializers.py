from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.utils import timezone
from rest_framework import exceptions
from rest_framework_simplejwt.tokens import Token
from rest_framework.validators import UniqueValidator
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from .utils import validate_otp, generate_otp, send_account_activation_otp


class UserEmailUniqueValidator(UniqueValidator):
    message = "User with the provided email already exists"
class UserPhoneUniqueValidator(UniqueValidator):
    message = "User with the provided Phonenumber already exists"






class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        User = get_user_model()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Invalid email"})

        # If user exists but is not active
        if not user.is_active:
            otp = generate_otp()
            user.otp = otp
            user.otp_expiry = timezone.now()
            user.save()

            send_account_activation_otp(user.email, otp)

            return {
                "email": "Account not verified. OTP sent to your email.",
                "is_active": user.is_active,
            }

        # If user is active → check password
        if not user.check_password(password):
            raise serializers.ValidationError({
                "password": "Invalid password"
            })

        # Generate tokens if all good
        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "is_active": user.is_active,
        }











class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[
            UserEmailUniqueValidator(queryset=get_user_model().objects.all())
        ],
    )

    phone_number = PhoneNumberField()

    password = serializers.CharField(
        write_only=True,
        required=True,
    )
    first_name = serializers.CharField( 
        required=True
        )

    last_name = serializers.CharField(
        required=True
        )

    class Meta:
        model = get_user_model()
        fields = (
            "password",
            "first_name",
            "last_name",
            "email",
            "phone_number",
        )
        extra_kwargs = {
            "email": {"required": True},
            "password": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
            "phone_number": {"reqired": True},
        }

    def validate(self, attrs):
        try:
            validate_password(password=attrs["password"], user = None)
        except ValidationError as err:
            raise serializers.ValidationError(err.messages)

        return attrs

    def create(self, validated_data):
        user = get_user_model().objects.create(
            email=validated_data["email"],
            first_name = validated_data['first_name'],
            last_name = validated_data['last_name'],
            phone_number = validated_data['phone_number']
            )

        user.set_password(validated_data["password"])
        otp = generate_otp()
        user.otp = otp
        user.otp_expiry = timezone.now()
        user.save()
        send_account_activation_otp(validated_data.get("email"), otp)

        return user

class AccountActivationSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate(self, attrs):
        otp = attrs['otp']
        user = validate_otp(otp)
        attrs['user'] = user
        
        return attrs
    
    def save(self,**kwargs):
        user = self.validated_data['user']
        user.is_active = True
        user.save(update_fields=["is_active"])

        return user

            


class ResendAccountActivationSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, attrs):
        user = (
            get_user_model()
            .objects.filter(email=attrs["email"])
            .first()
        )
        if user is None:
            raise serializers.ValidationError(
                {"email": "No user with the given email."}
            )
        else:
            otp = generate_otp()
            user.otp = otp
            user.otp_expiry = timezone.now()
            user.save()
            send_account_activation_otp(attrs["email"], otp)
            return attrs



class UserPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()


class UserConfirmPasswordResetSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(min_length=5, max_length=5)

    def validate(self, attrs):        
        try:
            validate_password(password=attrs.get("new_password"), user = None)
        except ValidationError as err:
            raise serializers.ValidationError(err.messages)

        return attrs
  




class UserUpdateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        validators=[
            UserEmailUniqueValidator(queryset=get_user_model().objects.all())
        ],
    )

    phone_number = PhoneNumberField(
        validators=[
            UserPhoneUniqueValidator(queryset=get_user_model().objects.all())
        ],)

    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'phone_number', 'email', 'address', 'avatar']


    