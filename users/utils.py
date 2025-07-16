from django.conf import settings
from django.utils.timezone import now
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse
from django.core.signing import TimestampSigner 
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

signer = TimestampSigner()

def send_confirmation_email(user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    link = f"http://localhost:8000/users/verify-email/{uid}/{token}/"
    html_content = render_to_string('users/confirmation_email.html', {
        'username': user.username,
        'confirmation_link': link
    })
    text_content = strip_tags(html_content)
    email = EmailMultiAlternatives(
        subject = 'Confirm Email',
        body = text_content,
        from_email = settings.DEFAULT_FROM_EMAIL,
        to = [user.email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


# Send confirmation success email

def send_confirmation_success_email(user):
    html_content = render_to_string('users/confirmation_success_email.html',{
        'username': user.username,
    })
    text_content = (
        f"Hi {user.username},\n\n"
        f"Your email has been successfully verified and your account is now active.\n\n"
        f"Regards,\nFreeWill Users"
    )
    email = EmailMultiAlternatives(
        subject = 'Welcome to FreeWill', 
        body = text_content, 
        from_email = settings.DEFAULT_FROM_EMAIL, 
        to = [user.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()

# Send login email

def send_login_email(user, request):
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    html_content = render_to_string('users/login_email.html', {
        'username': user.username,
        'ip': ip,
        'timestamp': timestamp,
        'user_agent': user_agent,
    })
    text_content = (
        f"Hi {user.username},\n\n"
        f"You recently logged into your account.\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nFreeWill Users"
    )
    email = EmailMultiAlternatives(
        subject='Logged into FreeWill',
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()

# Send profile update email

def send_profile_update_email(user, request, changes):
    ip = get_client_ip(request)
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    changes_str = "\n".join(
        f"- {field}: '{old}' → '{new}'" for field, (old, new) in changes.items()
    )
    html_content = render_to_string('users/profile_update_email.html', {
        'username': user.username,
        'changes': changes_str,
        'ip': ip,
        'timestamp': timestamp,
        'user_agent': user_agent,
    })
    text_content = (
        f"Hi {user.username},\n\n"
        f"Your account profile was updated with the following changes:\n"
        f"{changes_str}\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nFreeWill Users"
    )
    email = EmailMultiAlternatives(
        subject = 'Your profile was updated',
        body = text_content,
        from_email = settings.DEFAULT_FROM_EMAIL,
        to = [user.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


# Send email change email

def send_email_change_email(user, request, new_email):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    confirmation_link = request.build_absolute_uri(reverse('users:confirm_email_change', args=[uid, token]))
    html_content = render_to_string('users/email_change_email.html', {
        'username': user.first_name or user.username,
        'confirmation_link': confirmation_link,
    })
    text_content = (
        f"Hi {user.first_name or user.username},\n\n"
        f"You requested to change your email.\n"
        f"Please confirm this change by clicking the link below:\n\n{confirmation_link}\n\n"
        f"If you don't recognise this action, ignore this email. Someone likely typed in the wrong email.\n\n"
        f"Regards,\nFreeWill Users"
    )
    email = EmailMultiAlternatives(
        subject = 'Confirm your new email address',
        body = text_content,
        from_email = settings.DEFAULT_FROM_EMAIL,
        to = [new_email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()

# Send password change email

def send_email_change_success_email(user, request, new_email):
    ip = get_client_ip(request)
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    html_content = render_to_string('users/email_change_success_email.html', {
        'username': user.username,
        'new_email': new_email,
        'ip': ip,
        'timestamp': timestamp,
        'user_agent': user_agent,
    })
    text_content = (
        f"Hi {user.username},\n\n"
        f"Your account email was successfully changed to {new_email}.\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nFreeWill Users"
    )
    email = EmailMultiAlternatives(
        subject = 'Your email was changed',
        body = text_content,
        from_email = settings.DEFAULT_FROM_EMAIL,
        to = [user.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()

# Send password change email

def send_password_change_email(user, request):
    ip = get_client_ip(request)
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    html_content = render_to_string('users/password_change_email.html', {
        'username': user.username,
        'ip': ip,
        'timestamp': timestamp,
        'user_agent': user_agent,
    })
    text_content = (
        f"Hi {user.username},\n\n"
        f"Your account password was successfully changed.\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nFreeWill Users"
    )
    email = EmailMultiAlternatives(
        subject = 'Your password was changed',
        body = text_content,
        from_email = settings.DEFAULT_FROM_EMAIL,
        to = [user.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()

# Send delete account email

def send_delete_account_email(user, request):
    token = signer.sign(str(user.id))
    confirm_url = request.build_absolute_uri(
        reverse('users:confirm_delete_account') + f'?token={token}'
    )
    ip = get_client_ip(request)
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    html_content = render_to_string('users/delete_account_email.html', {
        'username': user.username,
        'confirm_url': confirm_url,
        'ip': ip,
        'timestamp': timestamp,
        'user_agent': user_agent,
    })
    text_content = (
        f"Hi {user.username},\n\n"
        f"Click the link below to confirm deletion of your account:\n\n"
        f"{confirm_url}\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nFreeWill Users"
    )
    email = EmailMultiAlternatives(
        subject = 'Confirm Your Account Deletion',
        body = text_content,
        from_email = settings.DEFAULT_FROM_EMAIL,
        to = [user.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()

# Send delete account success email

def send_delete_account_success_email(token, request):
    user_id = signer.unsign(token, max_age=60 * 60)
    user = User.objects.get(id=user_id)
    ip = get_client_ip(request)
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    html_content = render_to_string('users/delete_account_success_email.html', {
        'username': user.username,
        'ip': ip,
        'timestamp': timestamp,
        'user_agent': user_agent,
    })
    text_content = (
        f"Hi {user.username},\n\n"
        f"Your account has been successfully deleted.\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nFreeWill Users"
    )
    email = EmailMultiAlternatives(
        subject = 'Account Deletion Successful',
        body = text_content,
        from_email = settings.DEFAULT_FROM_EMAIL,
        to = [user.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()
    
# Get IP

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'Unknown')
    return ip