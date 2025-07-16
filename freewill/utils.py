from .models import GroupLog
from django.utils.timezone import now

def log_event(group, user, event_type, message=""):
    GroupLog.objects.create(
        group=group,
        user=user,
        event_type=event_type,
        message=message,
        timestamp=now().strftime("%Y-%m-%d %H:%M:%S %Z"),
    )