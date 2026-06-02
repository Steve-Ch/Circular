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
import requests
import resend
from django.template.loader import render_to_string
from datetime import datetime
from resend import Emails
import re


resend.api_key = settings.RESEND_API_KEY


def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    # if not re.search(r"[a-z]", password):
    #     return False, "Password must contain at least one lowercase letter."
    # if not re.search(r"\d", password):
    #     return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?`~]", password):
        return False, "Password must contain at least one special character."
    return True, 'success!'






def send_email_with_html(subject, context, html_template_path, recipient_list):
    # Render the HTML template with context
    html_content = render_to_string(html_template_path, context)
    
    # Fallback plain text version (optional)
    text_content = f"{subject}"  # Or generate a plain version of the message
    #from_email = f'Circular Team <{from_email}>'
    # Compose the email
    #email = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
    #email.attach_alternative(html_content, "text/html")

    

    try:
        Emails.send({
        "from": f"Circular <{settings.RESEND_SENDER_EMAIL}>",
        "to": recipient_list,
        "subject": subject,
        "html": html_content
    })
    except Exception as e:
        print("Failed to send email:", e)


def send_email_in_thread(subject, context, html_template_path, recipient_list,support=True):
    context['support']=support
    # Start a new thread to send the email
    email_threading = threading.Thread(
        target=send_email_with_html,
        args=(subject, context, html_template_path, recipient_list)
    )
    email_threading.start()



def send_account_activation_otp(email, otp):
    subject = "Activate Your Circular Account"
    recipient_list = [email]
    message = f"""
            Thank you for joining Circular estate shopping platform. You’re one step away from placing your first order.
            Use the OTP below to activate your account and begin your journey"""

    context={'title':'Welcome to Circlur , Let’s Get Started','otp': otp, message : message,'year': datetime.now().year}
    html_template_path="email/mail_template.html",
    send_email_in_thread(subject,context,html_template_path,recipient_list)


def send_reset_password_otp(email, otp):
    subject = "Your OTP for Password Reset"
    recipient_list = [email]
    context={'title':'Password Reset','otp': otp,'year': datetime.now().year}
    html_template_path="email/mail_template.html",
    send_email_in_thread(subject,context,html_template_path,recipient_list)

#general mail function
def send_html_mail(email, subject, message, title=None, support=True, otp=None):
    if title is None:
        title = subject
        
    # ✅ FIX: Handle both single email strings and lists/tuples of emails safely
    if isinstance(email, (list, tuple)):
        recipient_list = list(email)
    else:
        recipient_list = [email]
        
    context = {
        'title': title, 
        'message': message, 
        'year': datetime.now().year, 
        'otp': otp
    }
    
    html_template_path = "email/mail_template.html" 
    
    send_email_in_thread(subject, context, html_template_path, recipient_list, support)



def generate_otp(length=6):
    characters = string.digits
    otp = "".join(random.choice(characters) for _ in range(length))
    return otp


def validate_otp(otp, email, minutes=5):
    User = get_user_model()

    try:
        user = User.objects.get(email=email, otp=otp)
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

