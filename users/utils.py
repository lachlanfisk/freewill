from django.core.mail import send_mail
from django.conf import settings
from django.utils.timezone import now
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.urls import reverse
from django.core.signing import TimestampSigner 
from django.contrib.auth.models import User
from django.core.mail import send_mail

signer = TimestampSigner()

# Send confirmation email

def send_confirmation_email(user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    link = f"http://localhost:8000/users/verify-email/{uid}/{token}/"
    subject = 'Confirm your email address'
    message =(
        f"Hi {user.username},\n\n"
        f"Thanks for registering! Please confirm your email address by clicking the link below:\n\n"
        f"{link}\n\n"
        f"Regards,\nLF Project"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

# Send confirmation success email

def send_confirmation_success_email(user):
    subject = 'Welcome to LF Project!'
    message =(
        f"Hi {user.username},\n\n"
        f"Your email has been successfully verified and your account is now active.\n\n"
        f"Regards,\nLF Project"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

# Send login email

def send_login_email(user, request):
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    subject = 'Logged into LF Project'
    message = (
        f"Hi {user.username},\n\n"
        f"You recently logged into your account.\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nLF Project"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

# Send profile update email

def send_profile_update_email(user, request, changes):
    ip = get_client_ip(request)
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    subject = 'Your profile was updated'
    changes_str = "\n".join(
        f"- {field}: '{old}' → '{new}'" for field, (old, new) in changes.items()
    )
    message = (
        f"Hi {user.username},\n\n"
        f"Your account profile was updated with the following changes:\n"
        f"{changes_str}\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nLF Project"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

# Send email change email

def send_email_change_email(user, request, new_email):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = request.build_absolute_uri(
        reverse('users:confirm_email_change', args=[uid, token])
    )
    ip = get_client_ip(request)
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    subject = 'Confirm your new email address'
    message = (
        f"Hi {user.first_name or user.username},\n\n"
        f"You requested to change your email to {new_email}.\n"
        f"Please confirm this change by clicking the link below:\n\n{link}\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nLF Project"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [new_email],
        fail_silently=False,
    )

# Send password change email

def send_email_change_success_email(user, request, new_email):
    ip = get_client_ip(request)
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    subject = 'Your email was changed'
    message = (
        f"Hi {user.username},\n\n"
        f"Your account email was successfully changed to {new_email}.\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nLF Project"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

# Send password change email

def send_password_change_email(user, request):
    ip = get_client_ip(request)
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    subject = 'Your password was changed'
    message = (
        f"Hi {user.username},\n\n"
        f"Your account password was successfully changed.\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nLF Project"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

# Send delete account email

def send_delete_account_email(user, request):
    token = signer.sign(str(user.id))
    confirm_url = request.build_absolute_uri(
        reverse('users:confirm_delete_account') + f'?token={token}'
    )
    ip = get_client_ip(request)
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    subject = 'Confirm Your Account Deletion'
    message=(
        f"Hi {user.username},\n\n"
        f"Click the link below to confirm deletion of your account:\n\n"
        f"{confirm_url}\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nLF Project"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

# Send delete account success email

def send_delete_account_success_email(token, request):
    user_id = signer.unsign(token, max_age=60 * 60)  # token valid for 1 hour
    user = User.objects.get(id=user_id)
    ip = get_client_ip(request)
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    subject = 'Account Deletion Successful'
    message=(
        f"Hi {user.username},\n\n"
        f"Your account has been successfully deleted.\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nLF Project"
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    
# Get IP

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'Unknown')
    return ip