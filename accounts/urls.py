from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    CustomTokenObtainPairView,
    RegisterationView,
    AccountActivationView,
    UserResendActivationView,
    UserPasswordResetView,
    UserConfirmPasswordResetView,
    UpdateUserView,
)

urlpatterns = [
    # path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', RegisterationView.as_view()),
    path('activate/', AccountActivationView.as_view()),
    path('resend-activation-otp/', UserResendActivationView.as_view()),
    path('password-reset/', UserPasswordResetView.as_view()),
    path('confirm-password-reset/', UserConfirmPasswordResetView.as_view()),
    path('my-profile/', UpdateUserView.as_view()),
]
