from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.models import User
from .forms import GroupCreationForm, CommentForm
import urllib.parse
from .models import GroupJoinRequest, Group, Comment, GroupMember

@login_required
def home(request):
    user = request.user

    # Get the groups the user is in
    user_groups = Group.objects.filter(group_memberships__user=user)

    # Get public/invite-only groups the user is NOT in
    available_groups = Group.objects.exclude(id__in=user_groups).filter(visibility__in=['public', 'invite'])

    # Get join requests
    user_join_requests = GroupJoinRequest.objects.filter(user=user)

    # Get pending invitations
    pending_invitations = user.pending_invitations.all()

    return render(request, 'freewill/home.html', {
        'user_groups': user_groups,
        'available_groups': available_groups,
        'user_join_requests': user_join_requests,
        'pending_invitations': pending_invitations,
    })

@login_required
def group_detail(request, group_id, edit_comment_id=None):
    group = get_object_or_404(Group, id=group_id)
    banned_users = group.banned_users.all()

    # Determine user role
    if request.user == group.owner:
        user_role = 'owner'
    else:
        try:
            membership = GroupMember.objects.get(group=group, user=request.user)
            user_role = membership.role
        except GroupMember.DoesNotExist:
            messages.error(request, "You are not a member of this group.")
            return redirect('freewill:home')

    group_memberships = GroupMember.objects.filter(group=group).select_related('user')
    comments = group.comments.all().order_by('-created_at')

    comment_to_edit = None
    if edit_comment_id:
        comment_to_edit = get_object_or_404(Comment, id=edit_comment_id)
        if comment_to_edit.user != request.user and user_role not in ['admin', 'owner']:
            return redirect('freewill:group_detail', group_id=group.id)

    if request.method == 'POST':
        if comment_to_edit:
            form = CommentForm(request.POST, instance=comment_to_edit)
        else:
            form = CommentForm(request.POST)

        if form.is_valid():
            if user_role in ['comment', 'admin', 'owner']:  # Only these can post
                comment = form.save(commit=False)
                comment.user = request.user
                comment.group = group
                comment.save()
                return redirect('freewill:group_detail', group_id=group.id)
            else:
                messages.error(request, "You don't have permission to comment.")
                return redirect('freewill:group_detail', group_id=group.id)
    else:
        form = CommentForm(instance=comment_to_edit) if comment_to_edit else CommentForm()

    return render(request, 'freewill/group_detail.html', {
        'group': group,
        'comments': comments,
        'form': form,
        'comment_to_edit': comment_to_edit,
        'user_role': user_role,
        'group_memberships': group_memberships,
        'banned_users': banned_users,
    })

@login_required
def create_group(request):
    if request.method == 'POST':
        form = GroupCreationForm(request.POST, user=request.user)
        if form.is_valid():
            group_name = form.cleaned_data['name']
            if Group.objects.filter(name=group_name).exists():
                messages.error(request, f'A group with the name "{group_name}" already exists.')
            else:
                group = form.save()
                messages.success(request, f'Group "{group_name}" created successfully!')
                return redirect('freewill:group_detail', group_id=group.id)
    else:
        form = GroupCreationForm(user=request.user)
    return render(request, 'freewill/create_group.html', {'form': form})

@login_required
def edit_group_settings(request, group_id):
    group = get_object_or_404(Group, id=group_id)

    # Only the group owner can edit settings
    if request.user != group.owner:
        messages.error(request, "Only the group owner can edit settings.")
        return redirect('freewill:group_detail', group_id=group.id)

    if request.method == 'POST':
        form = GroupCreationForm(request.POST, instance=group, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Group settings updated.')
            return redirect('freewill:group_detail', group_id=group.id)
    else:
        form = GroupCreationForm(instance=group, user=request.user)

    return render(request, 'freewill/group_settings.html', {'form': form, 'group': group})

@login_required
def join_public_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)

    if request.user in group.banned_users.all():
        messages.error(request, "You are banned from this group.")
        return redirect('freewill:home')

    if group.visibility != 'public':
        messages.error(request, "This group is not public.")
        return redirect('freewill:home', group_id=group.id)

    if request.user in group.members.all():
        messages.info(request, "You are already a member of this group.")
    else:
        group.members.add(request.user)
        messages.success(request, f"You have joined the group '{group.name}'.")
    return redirect('freewill:group_detail', group_id=group.id)

@login_required
def manage_member_action(request, group_id, user_id):
    group = get_object_or_404(Group, id=group_id)
    target_user = get_object_or_404(User, id=user_id)

    # Ensure the current user has permission
    acting_member = GroupMember.objects.filter(group=group, user=request.user).first()
    target_member = GroupMember.objects.filter(group=group, user=target_user).first()
    action = request.POST.get('role')

    if not acting_member or acting_member.role not in ['admin', 'owner']:
        messages.error(request, "You don't have permission to manage members.")
        return redirect('freewill:group_detail', group_id=group.id)

    # Prevent modifying the owner
    if target_user == group.owner:
        messages.error(request, "You cannot modify the group owner.")
        return redirect('freewill:group_detail', group_id=group.id)

    # Admins can't manage other admins/owners
    if acting_member.role == 'admin' and target_member and target_member.role in ['admin', 'owner']:
        messages.error(request, "Admins can't modify other admins or the owner.")
        return redirect('freewill:group_detail', group_id=group.id)

    # Process actions
    if action in ['read', 'comment', 'admin']:
        if target_member:
            target_member.role = action
            target_member.banned = False
            target_member.save()
            messages.success(request, f"{target_user.username}'s role updated to {action}.")
    elif action == 'kick':
        GroupMember.objects.filter(group=group, user=target_user).delete()
        messages.success(request, f"{target_user.username} has been removed from the group.")
    elif action == 'ban':
        GroupMember.objects.filter(group=group, user=target_user).delete()
        group.banned_users.add(target_user)
        messages.success(request, f"{target_user.username} has been banned from the group.")
    else:
        action = request.GET.get('action') or request.POST.get('role')
        if action == 'unban':
            group.banned_users.remove(target_user)
            messages.success(request, f'{target_user.username} has been unbanned.')
        else:
            messages.error(request, "Invalid action.")

    return redirect('freewill:group_detail', group_id=group.id)

@login_required
def leave_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    # Check if the user is a member of the group
    if request.user in group.members.all():
        group.members.remove(request.user)  # Remove the user from the group
        messages.success(request, f'You have left the group {group.name}.')
    else:
        messages.error(request, 'You are not a member of this group.') 
    return redirect('freewill:home') 

@login_required
def transfer_ownership(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    if request.user != group.owner:
        return redirect('freewill:group_detail', group_id=group.id)
    admin_members = GroupMember.objects.filter(group=group, role='admin').exclude(user=group.owner)

    if request.method == 'POST':
        new_owner_id = request.POST.get('new_owner_id')
        try:
            new_owner = User.objects.get(id=new_owner_id)
            if not admin_members.filter(user=new_owner).exists():
                messages.error(request, "Selected user must be an admin.")
                return redirect('freewill:transfer_ownership', group_id=group.id)

            # Transfer ownership
            group.owner = new_owner
            group.save()

            # Optionally downgrade the old owner to 'comment'
            old_owner_membership = GroupMember.objects.get(user=request.user, group=group)
            old_owner_membership.role = 'comment'
            old_owner_membership.save()

            messages.success(request, f"Ownership transferred to {new_owner.profile.nickname}.")
            return redirect('freewill:group_detail', group_id=group.id)

        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect('freewill:transfer_ownership', group_id=group.id)

    return render(request, 'freewill/transfer_ownership.html', {
        'group': group,
        'admin_members': admin_members,
    })

@login_required
def delete_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    if request.user == group.owner:
        group.delete()
        messages.success(request, "Group deleted.")
    else:
        messages.error(request, "Only the owner can delete this group.")
    return redirect('freewill:home')

#----------------------------------------------------- Invite Only ---------------------------------------------

@login_required
def invite_users(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    is_owner = request.user == group.owner
    is_admin = GroupMember.objects.filter(group=group, user=request.user, role='admin').exists()
    if not (is_owner or is_admin):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('freewill:group_detail', group_id=group.id)
    
    users_not_in_group = User.objects.exclude(
        id__in=group.members.values_list('id', flat=True)
    ).exclude(
        id__in=group.banned_users.values_list('id', flat=True)
    )

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        invited_user = get_object_or_404(User, id=user_id)      
        if invited_user in group.invited_users.all():
            messages.info(request, f'{invited_user.profile.nickname} has already been invited.')
        else:
            group.invited_users.add(invited_user)
            messages.success(request, f'Invitation sent to {invited_user.profile.nickname}.')
        return redirect('freewill:group_detail', group_id=group.id)  
    return render(request, 'freewill/invite_users.html', {
        'group': group,
        'users_not_in_group': users_not_in_group
    })

@login_required
def respond_to_invite(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    user_id = request.GET.get('user_id')
    action = request.GET.get('action')  # 'accept' or 'deny'

    if request.user in group.banned_users.all():
        messages.error(request, "You are banned from this group.")
        return redirect('freewill:home')

    if not user_id or str(request.user.id) != user_id:
        messages.error(request, "Invalid invitation link.")
        return redirect('freewill:home')

    if request.user not in group.invited_users.all():
        messages.error(request, "You are not invited to this group.")
        return redirect('freewill:home')

    if action == 'accept':
        group.members.add(request.user)
        group.invited_users.remove(request.user)
        messages.success(request, f'You have successfully joined the group "{group.name}".')
    elif action == 'deny':
        group.invited_users.remove(request.user)
        messages.info(request, f'You have declined the invitation to join "{group.name}".')
    else:
        messages.error(request, "Invalid action.")
    
    return redirect('freewill:home')

@login_required
def request_to_join_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)

    if request.user in group.banned_users.all():
        messages.error(request, "You are banned from this group.")
        return redirect('freewill:home')

    # Disallow joining if not invite-only
    if group.visibility != 'invite':
        messages.error(request, "You cannot request to join this group.")
        return redirect('freewill:home')

    if request.user in group.members.all():
        messages.info(request, "You are already a member of this group.")
        return redirect('freewill:home')

    join_request, created = GroupJoinRequest.objects.get_or_create(user=request.user, group=group)
    if created:
        messages.success(request, "Your request to join the group has been submitted.")
    else:
        messages.info(request, "You have already requested to join this group.")
    return redirect('freewill:home')

@login_required
def delete_join_request(request, request_id):
    join_request = get_object_or_404(GroupJoinRequest, id=request_id, user=request.user)
    # Ensure the logged-in user can only delete their own join requests
    if join_request.user == request.user:
        join_request.delete()
        messages.success(request, "Your join request has been successfully deleted.")
    else:
        messages.error(request, "You are not authorised to delete this join request.")
    return redirect('freewill:home')   

@login_required
def handle_join_request(request, group_id, request_id, action):
    group = get_object_or_404(Group, id=group_id)
    is_owner = request.user == group.owner
    is_admin = GroupMember.objects.filter(group=group, user=request.user, role='admin').exists()
    if not (is_owner or is_admin):
        messages.error(request, "Only the group admin can manage join requests.")
        return redirect('freewill:group_detail', group_id=group.id)
    group = get_object_or_404(Group, id=group_id)
    join_request = get_object_or_404(GroupJoinRequest, id=request_id)
    if action == 'approve':
        group.members.add(join_request.user)
        join_request.delete()
        messages.success(request, f"{join_request.user.profile.nickname} has been added to the group.")
    elif action == 'reject':
        join_request.delete()
        messages.info(request, f"{join_request.user.profile.nickname}'s join request has been rejected.")
    else:
        messages.error(request, "Invalid action.")
    
    return redirect('freewill:group_detail', group_id=group.id)

#---------------------------------------------- Comments -----------------------------------------------------

@login_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if comment.user != request.user:  # Ensure only the comment author can edit
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('freewill:group_detail', group_id=comment.group.id)
    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            return redirect('freewill:group_detail', group_id=comment.group.id)
    else:
        form = CommentForm(instance=comment)
    return render(request, 'freewill/edit_comment.html', {'form': form, 'comment': comment})

@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if (
        comment.user == request.user or
        request.user == comment.group.owner or
        GroupMember.objects.filter(group=comment.group, user=request.user, role='admin').exists()
    ):  # Allow author or group admin to delete
        comment.delete()
    return redirect('freewill:group_detail', group_id=comment.group.id)

