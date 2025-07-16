from django.db import models
from django.contrib.auth.models import User

class GroupMember(models.Model):
    ROLE_CHOICES = [
        ('read', 'Read-Only'),
        ('comment', 'Comment'),
        ('admin', 'Admin'),
        ('owner', 'Owner'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey('Group', on_delete=models.CASCADE, related_name='group_memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='read')
    banned = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'group')

class Group(models.Model):
    VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('invite', 'Invite-Only'),
        ('hidden', 'Hidden'),
    ]
    DEFAULT_ROLE_CHOICES = [
        ('read', 'Read-Only'),
        ('comment', 'Comment'),
    ]
    
    default_role = models.CharField(max_length=10, choices=DEFAULT_ROLE_CHOICES, default='read')
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_groups', default=29)
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default='public')
    members = models.ManyToManyField(User, through='GroupMember')
    invited_users = models.ManyToManyField(User, related_name='pending_invitations', blank=True)
    banned_users = models.ManyToManyField(User, related_name='banned_from_groups', blank=True)

    def __str__(self):
        return self.name

class GroupJoinRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='join_requests')
    is_approved = models.BooleanField(default=False)
    votes = models.ManyToManyField(User, related_name='votes', blank=True)  # Tracks users who voted
    created_at = models.DateTimeField(auto_now_add=True)

class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # User who posted the comment
    group = models.ForeignKey(Group, related_name='comments', on_delete=models.CASCADE)  # Group associated with the comment
    content = models.TextField()  # The comment content
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp when the comment was posted
    updated_at = models.DateTimeField(auto_now=True)  # Timestamp for the latest update

    def __str__(self):
        return f"{self.user.username}: {self.content[:20]}..."  # Show only first 20 chars for preview

class GroupLog(models.Model):
    EVENT_CHOICES = [
        ('created', 'Group Created'),
        ('joined', 'User Joined'),
        ('left', 'User Left'),
        ('comment_edited', 'Comment Edited'),
        ('comment_deleted', 'Comment Deleted'),
        ('invited', 'User Invited'),
        ('invite_accepted', 'Invite Accepted'),
        ('invite_denied', 'Invite Denied'),
        ('join_requested', 'Join Requested'),
        ('join_request_deleted', 'Join Request Deleted'),
        ('join_request_accepted', 'Join Request Accepted'),
        ('join_request_denied', 'Join Request Denied'),
        ('role_changed', 'Role Changed'),
        ('kicked', 'User Kicked'),
        ('banned', 'User Banned'),
        ('unbanned', 'User Unbanned'),
        ('updated', 'Group Updated'),
        ('ownership_transferred', 'Ownership Transferred'),
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='log_entries')
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
