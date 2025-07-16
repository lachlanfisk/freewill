from .models import GroupMember

def get_user_role(group, user):
    try:
        return GroupMember.objects.get(group=group, user=user).role
    except GroupMember.DoesNotExist:
        return None

def can_comment(group, user):
    role = get_user_role(group, user)
    return role in ['comment', 'admin']

def is_admin(group, user):
    return get_user_role(group, user) == 'admin'

def is_owner(group, user):
    return group.owner == user