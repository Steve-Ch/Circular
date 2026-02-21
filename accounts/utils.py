from datetime import timedelta
import time
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
import random
import string
import threading
from rest_framework.exceptions import ValidationError



def send_email_in_thread(subject,message,from_email,recipient_list):
    email_threading=threading.Thread(target=send_mail,args=(subject,message,from_email,recipient_list))
    email_threading.start()
    send_mail(subject,message,from_email,recipient_list)


def generate_otp(length=6):
    characters = string.digits
    otp = "".join(random.choice(characters) for _ in range(length))
    return otp


# def validate_otp(otp, minutes=5):
#     try:
#         user = get_user_model().objects.get(otp=otp)
#     except get_user_model().DoesNotExist:
#         return None
#     time_diff = timezone.now() - user.otp_expiry
#     if user.otp == otp and time_diff < timedelta(minutes=minutes):
#         user.otp = None
#         user.otp_expiry = None
#         return user

def validate_otp(otp, minutes=5):
    User = get_user_model()

    try:
        user = User.objects.get(otp=otp)
    except User.DoesNotExist:
        raise ValidationError("Invalid OTP.")

    if timezone.now() - user.otp_expiry > timedelta(minutes=minutes):
        raise ValidationError("OTP has expired.")

    if user.otp != otp:
        raise ValidationError("Incorrect OTP.")

    # Invalidate OTP after successful use
    user.otp = None
    user.otp_expiry = None
    user.save(update_fields=["otp", "otp_expiry"])

    return user

# def send_otp_by_phone(phone_number,otp):
#     account_sid="your_account_id"
#     auth_token="your_auth_token"
#     twilio_phone_number="your_twilio_phone_number"

#     client=Client(account_sid,auth_token)
#     message=client.messages.create(
#        body=f"Your OTP is: {otp}",
#        from_=twilio_phone_number,
#        to=phone_number

#     )


# def send_verify_email_otp(email, otp):
#     subject = "Your OTP for Email Verification"
#     message = f"Your OTP is: {otp}"
#     from_email = settings.EMAIL_HOST_USER
#     recipient_list = [email]
#     sendreset_password_otp(email, otp):
#     subject = "Your OTP for Password Reset"
#     message = f"Your OTP is: {otp}. It is valid for 10mins"
#     from_email = settings.EMAIL_HOST_USER
#     recipient_list = [email]
#     send_email_in_thread(subject, message, from_email, recipient_list)


# def send_reset_pin_otp(email, otp):
#     subject = "Your OTP for PIN Reset"
#     message = f"Your OTP is: {otp}. It is valid for 10mins"
#     from_email = settings.EMAIL_HOST_USER
#     recipient_list = [email]
#     send_email_in_thread(subject, message, from_email, recipient_list)




def send_account_activation_otp(email, otp):
    subject = "Your OTP for your account Activation/Deactivation"
    message = f"Your OTP is: {otp}.  It is valid for 5 minutes."
    from_email = settings.EMAIL_HOST_USER
    recipient_list = [email]
    send_email_in_thread(subject, message, from_email, recipient_list)

def send_reset_password_otp(email, otp):
    subject = "Your OTP for Password Reset"
    message = f"Your OTP is: {otp}. It is valid for 5 minutes"
    from_email = settings.EMAIL_HOST_USER
    recipient_list = [email]
    send_email_in_thread(subject, message, from_email, recipient_list)



