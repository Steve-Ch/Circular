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
from .utils import validate_otp, generate_otp, send_account_activation_otp, validate_password
from .models import Estate
from google.auth.exceptions import TransportError
import urllib3
from google.auth.transport.urllib3 import Request as Urllib3Request
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.conf import settings
from google.oauth2 import id_token
from phonenumber_field.serializerfields import PhoneNumberField
import jwt
from jwt.algorithms import RSAAlgorithm
from phonenumber_field.serializerfields import PhoneNumberField
import requests
from google.auth.transport import requests as google_requests

User = get_user_model()

class AppleAuthSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    
    # Required for new users completing registration
    phone_number = PhoneNumberField(required=False)
    estate = serializers.PrimaryKeyRelatedField(
        queryset=Estate.objects.all(), 
        required=False
    )
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False)

    def validate(self, attrs):
        token = attrs.get('token')
        
        try:
            # 1. Fetch Apple's live public keys
            apple_keys_url = "https://appleid.apple.com/auth/keys"
            response = requests.get(apple_keys_url)
            keys = response.json().get('keys')
            
            # 2. Extract key ID (kid) from the token's unverified header
            header = jwt.get_unverified_header(token)
            kid = header.get('kid')
            
            # 3. Find the matching key provided by Apple
            matching_key = next((key for key in keys if key['kid'] == kid), None)
            if not matching_key:
                raise serializers.ValidationError({"token": "Invalid Apple Key."})
                
            # 4. Construct the RSA Public Key
            public_key = RSAAlgorithm.from_jwk(matching_key)
            
            # 5. Decode and cryptographically verify the token
            decoded_token = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                audience=settings.APPLE_CLIENT_IDS, # Matches token to your Bundle ID / Service ID
                issuer="https://appleid.apple.com"
            )
            
            email = decoded_token.get('email')
            
        except jwt.ExpiredSignatureError:
            raise serializers.ValidationError({"token": "Apple token has expired."})
        except jwt.InvalidAudienceError:
            raise serializers.ValidationError({"token": "Unrecognized Apple Client ID. Access Denied."})
        except Exception as e:
            raise serializers.ValidationError({"token": f"Invalid Apple token: {str(e)}"})

        # 6. Check if the user already exists
        user = User.objects.filter(email__iexact=email).first()

        if user:
            # Activate them if not active
            if not user.is_active:
                user.is_active = True
                user.save(update_fields=['is_active'])
            
            attrs['user'] = user
            return attrs

        # 7. User does NOT exist. We need to create them.
        phone_number = attrs.get('phone_number')
        estate = attrs.get('estate')
        
        # We require these fields to complete the profile
        if not phone_number or not estate:
            raise serializers.ValidationError({
                "incomplete_profile": "Account does not exist. Please provide phone_number, estate, first_name, and last_name along with the Apple token to register."
            })

        # if User.objects.filter(phone_number=phone_number).exists():
        #     raise serializers.ValidationError({
        #         "phone_number": "This phone number is already registered."
        #     })

        # 8. Create the new user
        # Note: If the user used "Hide My Email", the email will look like 
        # "randomstring@privaterelay.appleid.com". This is normal and expected.
        user = User.objects.create(
            email=email,
            first_name=attrs.get('first_name', ''),
            last_name=attrs.get('last_name', ''),
            phone_number=phone_number,
            estate=estate,
            address=attrs.get('address', ''),
            is_active=True
        )
        
        user.set_unusable_password()
        user.save()

        attrs['user'] = user
        return attrs









class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    
    # Optional fields: only required if the user doesn't exist yet
    phone_number = PhoneNumberField(required=False)
    estate = serializers.PrimaryKeyRelatedField(
        queryset=Estate.objects.all(), 
        required=False
    )
    address = serializers.CharField(required=False)

    def validate(self, attrs):
        token = attrs.get('token')
        
        try:
            # # 1. Verify the Google Token
            # idinfo = id_token.verify_oauth2_token(
            #     token, 
            #     requests.Request(),
            #     audience=None 
            # )

            http = urllib3.PoolManager()
            request = Urllib3Request(http)

            idinfo = id_token.verify_oauth2_token(
                token, 
                google_requests.Request(), # Pass the urllib3 request object here instead
                audience=None 
            )
            
            # 2. Verify the token came from ONE of your trusted apps
            if idinfo['aud'] not in settings.GOOGLE_OAUTH2_CLIENT_IDS:
                raise serializers.ValidationError({"token": "Unrecognized Client ID. Access Denied."})

            email = idinfo['email']
            
        except ValueError:
            raise serializers.ValidationError({"token": "Invalid or expired Google token."})
        except TransportError:
            # Catch the network connection error
            raise serializers.ValidationError({"token": "Unable to verify token with Google due to network issues. Try again later."})
        # 3. Check if the user already exists
        user = User.objects.filter(email__iexact=email).first()

        if user:
            # If the user exists but hasn't activated their account,
            # Google verification is proof of email ownership, so we activate them.
            if not user.is_active:
                user.is_active = True
                user.save(update_fields=['is_active'])
            
            attrs['user'] = user
            return attrs

        # 4. User does NOT exist. We need to create them.
        # Check if the frontend provided the required phone_number and estate.
        phone_number = attrs.get('phone_number')
        estate = attrs.get('estate')

        if not phone_number or not estate:
            raise serializers.ValidationError({
                "incomplete_profile": "Account does not exist. Please provide phone_number and estate along with the Google token to register."
            })

        # Validate that the provided phone number isn't already used
        # if User.objects.filter(phone_number=phone_number).exists():
        #     raise serializers.ValidationError({
        #         "phone_number": "This phone number is already registered."
        #     })

        # 5. Create the new user
        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')

        user = User.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            estate=estate,
            address=attrs.get('address', ''),
            is_active=True  # Google already verified their email
        )
        
        # User signed up via Google, so they don't have a traditional password
        user.set_unusable_password()
        user.save()

        attrs['user'] = user
        return attrs
















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
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Invalid email or password"})

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
            raise serializers.ValidationError(
            "Invalid email or password"
            )

        # Generate tokens if all good
        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "is_active": user.is_active,
        }




class EstateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estate
        fields = ['id','name', 'address', 'state', 'town', 'longitude', 'latitude']





class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=True,
        validators=[
            UserEmailUniqueValidator(queryset=get_user_model().objects.all())
        ],
    )

    phone_number = PhoneNumberField(
        validators=[
            UserPhoneUniqueValidator(queryset=get_user_model().objects.all())
        ],
    )

    password = serializers.CharField(
        write_only=True,
        required=True,
    )
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    
    
    estate = serializers.PrimaryKeyRelatedField(
        queryset=Estate.objects.all(),
        required=True,
        error_messages={'does_not_exist': 'The selected estate ID does not exist in our system.',}
    )

    class Meta:
        model = get_user_model()
        fields = (
            "password",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "estate",
            "address",
        )
        extra_kwargs = {
            "email": {"required": True},
            "password": {"required": True},
            "first_name": {"required": True},
            "last_name": {"required": True},
            "phone_number": {"required": True},
            "address" : {"required": False} 
        }

    def validate(self, attrs):
        password = attrs['password']
        secure, message = validate_password(password)

        if not secure:
            raise serializers.ValidationError({"password": message})
        
        return attrs

    def create(self, validated_data):
        # 3. Pull the Estate instance out of validated_data
        estate_instance = validated_data.get("estate")

        # 4. Pass the estate instance directly into your create call
        user = get_user_model().objects.create(
            email=validated_data["email"],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            phone_number=validated_data['phone_number'],
            estate=estate_instance,  # Connects the user to the estate
            address=validated_data['address'], 
            
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
    email = serializers.EmailField()

    def validate(self, attrs):
        otp = attrs['otp']
        email = attrs['email']
        user = validate_otp(otp, email)
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
    new_password = serializers.CharField(min_length=8)
    email = serializers.EmailField(required=True)

    def validate(self, attrs):
        password = attrs['new_password']
        secure, message = validate_password(password)

        if not secure:
            raise serializers.ValidationError({"password": message})
        
        return attrs
  



class UserUpdateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        required=False, # Allows updating other fields without re-sending email
        validators=[
            UserEmailUniqueValidator(queryset=get_user_model().objects.all())
        ],
    )

    phone_number = PhoneNumberField(
        required=False, # Allows updating other fields without re-sending phone
        validators=[
            UserPhoneUniqueValidator(queryset=get_user_model().objects.all())
        ],
    )

    # Incorporating the estate field setup (Set to required=False for updates)
    estate = serializers.PrimaryKeyRelatedField(
        queryset=Estate.objects.all(),
        required=False,
        allow_null=True,  # Allows a user to clear/remove their estate if needed
        error_messages={
            'does_not_exist': 'The selected estate ID does not exist in our system.',
            'incorrect_type': 'Incorrect type. Expected an integer or ID representing the estate.'
        }
    )

    class Meta:
        model = get_user_model()
        fields = [
            'first_name',
            'last_name', 
            'email', 
            'phone_number', 
            'estate',  # Included in fields list
            'address', 
            'avatar'
        ]

    def validate(self, attrs):
        # Unique validation protection during updates
        user = self.instance  # Gets the user currently logged in / being updated
        
        # Prevent unique validators from crashing on the user's own current data
        if user:
            if 'email' in attrs and attrs['email'] == user.email:
                attrs.pop('email')  # Remove it from validation if it didn't change
            if 'phone_number' in attrs and attrs['phone_number'] == user.phone_number:
                attrs.pop('phone_number') # Remove it from validation if it didn't change

        return attrs


    