from django.http import HttpResponse 
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.models import User
from .forms import GroupCreationForm
from .models import Group
import urllib.parse
from .models import GroupJoinRequest
from .models import Group, Comment
from .forms import CommentForm

@login_required
def home(request):
    user = request.user

    # Invitations
    pending_invitations = user.pending_invitations.all()

    # Groups the user is already in
    user_groups = user.group_memberships.all()

    # Join requests already submitted by this user
    user_join_requests = GroupJoinRequest.objects.filter(user=user)

    # Public groups (anyone can join, so show all where the user is not a member)
    public_groups = Group.objects.filter(visibility='public').exclude(members=user)

    # Invite-only groups (only show if not a member and hasn't already requested)
    invite_only_groups = Group.objects.filter(visibility='invite') \
        .exclude(members=user) \
        .exclude(join_requests__user=user)

    # Hidden groups (only show if user is explicitly invited)
    hidden_groups = Group.objects.filter(visibility='hidden', invited_users=user)

    # Combine them all
    available_groups = (public_groups | invite_only_groups | hidden_groups).distinct()

    context = {
        'pending_invitations': pending_invitations,
        'user_groups': user_groups,
        'user_join_requests': user_join_requests,
        'available_groups': available_groups
    }

    return render(request, 'freewill/home.html', context)

@login_required
def group_detail(request, group_id, edit_comment_id=None):
    group = get_object_or_404(Group, id=group_id)
    if request.user not in group.members.all():
        messages.error(request, f'You do not have permission to join this group')
        return redirect('freewill:home')
    comments = group.comments.all().order_by('-created_at')  # Fetch all comments for the group
    if edit_comment_id: # Fetch the comment to edit, if edit_comment_id is provided
        comment_to_edit = get_object_or_404(Comment, id=edit_comment_id)
        if comment_to_edit.user != request.user:
            return redirect('freewill:group_detail', group_id=group.id)
    else:
        comment_to_edit = None
    if request.method == 'POST':
        if comment_to_edit: # Editing an existing comment
            form = CommentForm(request.POST, instance=comment_to_edit)
        else: # Adding a new comment
            form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            comment.group = group
            comment.save()
            return redirect('freewill:group_detail', group_id=group.id)
    else:
        form = CommentForm(instance=comment_to_edit) if comment_to_edit else CommentForm()
    return render(request, 'freewill/group_detail.html', {
        'group': group,
        'comments': comments,
        'form': form,
        'comment_to_edit': comment_to_edit,
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
def join_public_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)

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
def delete_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    if request.user == group.admin:
        group.delete()
        messages.success(request, f'Group "{group.name}" has been deleted.')
    else:
        messages.error(request, "You do not have permission to delete this group.")
    return redirect('freewill:home')

#----------------------------------------------------- Invite Only ---------------------------------------------

@login_required
def invite_users(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    users_not_in_group = User.objects.exclude(id__in=group.members.values_list('id', flat=True))
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
def accept_invite(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    user_id = request.GET.get('user_id')
    if user_id:
        invited_user = get_object_or_404(User, id=user_id)
        if invited_user in group.members.all():
            messages.info(request, f'{invited_user.profile.nickname} is already a member of the group "{group.name}".')
        elif invited_user in group.invited_users.all():
            group.members.add(invited_user)
            group.invited_users.remove(invited_user)  # Remove from invited list
            messages.success(request, f'{invited_user.profile.nickname} has successfully joined the group "{group.name}".')
        else:
            messages.error(request, "You are not invited to join this group.")
    else:
        messages.error(request, "Invalid invitation link.")  
    return redirect('freewill:group_detail', group_id=group.id)

@login_required
def request_to_join_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)

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
    join_request = get_object_or_404(GroupJoinRequest, id=request_id)

    if request.user != group.admin:
        messages.error(request, "Only the group admin can manage join requests.")
        return redirect('freewill:group_detail', group_id=group.id)

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
    if comment.user == request.user or request.user == comment.group.admin:  # Allow author or group admin to delete
        comment.delete()
    return redirect('freewill:group_detail', group_id=comment.group.id)

