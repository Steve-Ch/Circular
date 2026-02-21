from django.shortcuts import render
from django.contrib.auth import get_user_model
from rest_framework import generics, status,exceptions
from rest_framework.response import Response
from django.utils import timezone
from django.conf import settings
from rest_framework import permissions, parsers
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import (
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    AccountActivationSerializer, 
    ResendAccountActivationSerializer,
    UserPasswordResetSerializer,
    UserConfirmPasswordResetSerializer,
    UpdateProfileSerializer,
    )
from.utils import validate_otp, generate_otp, send_reset_password_otp,send_mail

# Create your views here.

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer



class RegisterationView(generics.GenericAPIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status= status.HTTP_201_CREATED)


class AccountActivationView(generics.GenericAPIView):
    def post(self, request):
        serializer = AccountActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Account Activated Successfully'}, status= status.HTTP_200_OK)
        

class UserResendActivationView(generics.GenericAPIView):
    serializer_class = ResendAccountActivationSerializer

    def post(self, request):
        serializer = ResendAccountActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response("New Activation OTP has been sent to your email")


class UserPasswordResetView(generics.GenericAPIView):
    serializer_class = UserPasswordResetSerializer

    def post(self, request):
        serializer = UserPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user=get_user_model().objects.get(email=serializer.validated_data.get("email"))
        except get_user_model().DoesNotExist:
            raise exceptions.NotAcceptable(
                "User with the given email does not exist."
            )
        
        otp = generate_otp()
        user.otp = otp
        user.otp_expiry = timezone.now()
        user.save()
        send_reset_password_otp(email=serializer.validated_data.get("email"), otp=otp)
        return Response(data="OTP has been Sent to your email. Expires in 5 minutes")



class UserConfirmPasswordResetView(generics.GenericAPIView):
    serializer_class = UserConfirmPasswordResetSerializer
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = UserConfirmPasswordResetSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            otp = serializer.validated_data.get("otp")
            new_password = serializer.validated_data.get("new_password")
            user = validate_otp(otp)
            user.set_password(new_password)
            user.save()
            send_mail(
                subject=f"Profiter Password Reset",
                message=f"Your password has been reset sucessfully",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[user.email],
            )
            return Response("Password reset successful.", status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UpdateUserView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes=[parsers.MultiPartParser]

    def patch(self, request):
        serializer = UpdateProfileSerializer(
            request.user, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Profile updated successfully."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)