from users.models import Profile
from .models import GroupInvitation

def pending_invitations(request):
    if request.user.is_authenticated:
        invites = GroupInvitation.objects.filter(invited_user=request.user)
        return {'pending_invitations': invites}
    return {}

def user_profile(request):
    if request.user.is_authenticated:
        try:
            return {'nickname': request.user.profile.nickname}
        except Profile.DoesNotExist:
            return {'nickname': request.user.username}  # Fallback to username if no profile exists
    return {}