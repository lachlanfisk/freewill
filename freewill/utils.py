from .models import GroupLog
from django.utils.timezone import now
from django.core.mail import send_mail
from users.utils import get_client_ip
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

def log_event(group, user, event_type, message=""):
    GroupLog.objects.create(
        group=group,
        user=user,
        event_type=event_type,
        message=message,
        timestamp=now().strftime("%Y-%m-%d %H:%M:%S %Z"),
    )

def send_transfer_ownership_email(user, request, group):
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    html_content = render_to_string('freewill/transfer_ownership_email.html', {
        'username': user.username,
        'group_name': group.name,
        'ip': ip,
        'timestamp': timestamp,
        'user_agent': user_agent,
    })
    text_content = (
        f"Hi {user.username},\n\n"
        f"You recently transferred ownership of group {group.name}.\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nFreeWill Social"
    )
    email = EmailMultiAlternatives(
        subject = 'Transferred Ownership',
        body = text_content,
        from_email = settings.DEFAULT_FROM_EMAIL,
        to = [user.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()

def send_delete_group_email(user, request, group):
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    timestamp = now().strftime("%Y-%m-%d %H:%M:%S %Z")
    html_content = render_to_string('freewill/delete_group_email.html', {
        'username': user.username,
        'group_name': group.name,
        'ip': ip,
        'timestamp': timestamp,
        'user_agent': user_agent,
    })
    text_content = (
        f"Hi {user.username},\n\n"
        f"You recently deleted group {group.name}.\n\n"
        f"Here are the details of the request:\n"
        f"- IP Address: {ip}\n"
        f"- Time: {timestamp}\n"
        f"- Device/Browser: {user_agent}\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nFreeWill Social"
    )
    email = EmailMultiAlternatives(
        subject = 'Deleted a group',
        body = text_content,
        from_email = settings.DEFAULT_FROM_EMAIL,
        to = [user.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send()
