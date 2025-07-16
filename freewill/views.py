from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .utils import send_transfer_ownership_email, send_delete_group_email
from .forms import GroupCreationForm, CommentForm
from .models import GroupJoinRequest, Group, Comment, GroupMember, GroupLog, GroupInvitation
from .utils import log_event

#-------------------------------------------- Group Creation and Joining --------------------------------------------

@login_required
def home(request):
    user = request.user
    user = request.user
    search_query = request.GET.get('search', '')  # <-- this line

    user_groups = Group.objects.filter(group_memberships__user=user)
    available_groups = Group.objects.exclude(id__in=user_groups).filter(visibility__in=['public', 'invite']).exclude(banned_users=user)

    if search_query:
        user_groups = user_groups.filter(
            Q(name__icontains=search_query) | Q(nickname__icontains=search_query)
        )
        available_groups = available_groups.filter(
            Q(name__icontains=search_query) | Q(nickname__icontains=search_query)
        )

    # Step 1: Get GroupMember records for the current user
    group_memberships = GroupMember.objects.select_related('group').filter(user=user)

    # Step 2: Apply search filter to GroupMember if neede

    # Step 3: Build list of groups with roles attached
    user_groups = []
    for membership in group_memberships:
        group = membership.group
        group.role = membership.role  # Attach the role to the group
        user_groups.append(group)

    # Step 4: Get available groups (not joined, visible, not banned)
    joined_group_ids = [group.id for group in user_groups]
    available_groups = Group.objects.exclude(id__in=joined_group_ids)\
        .filter(visibility__in=['public', 'invite'])\
        .exclude(banned_users=user)

    if search_query:
        available_groups = available_groups.filter(name__icontains=search_query)

    # Step 5: Get invitations
    pending_invitations = GroupInvitation.objects.filter(invited_user=user)

    user_groups = []
    for membership in group_memberships:
        user_groups.append({
            'group': membership.group,
            'role': membership.get_role_display()
        })

    return render(request, 'freewill/home.html', {
        'user_groups': user_groups,
        'available_groups': available_groups,
        'pending_invitations': pending_invitations,
        'search_query': search_query,
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
                log_event(group, request.user, 'created', f"Group Created; Name: {group.name}, Visibility: {group.visibility}, Default Permissions: {group.default_role}")
                messages.success(request, f'Group "{group_name}" created successfully!')
                return redirect('freewill:group_detail', group_id=group.id)
    else:
        form = GroupCreationForm(user=request.user)
    return render(request, 'freewill/create_group.html', {'form': form})

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
        log_event(group, request.user, 'joined', f"User joined the group")
        messages.success(request, f"You have joined the group '{group.name}'.")
    return redirect('freewill:group_detail', group_id=group.id)

@login_required
def group_detail(request, group_id):
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

    has_admin = GroupMember.objects.filter(group=group, role='admin').exists()
    return render(request, 'freewill/group_detail.html', {
        'group': group,
        'user_role': user_role,
        'group_memberships': group_memberships,
        'banned_users': banned_users,
        'has_admin': has_admin,
    })

@login_required
def available_groups(request):
    user = request.user

    # Get group IDs user is invited to, if GroupInvitation exists
    invited_group_ids = GroupInvitation.objects.filter(invited_user=user).values_list('group_id', flat=True)

    # Exclude groups user is already in, banned from, or invited to
    excluded_group_ids = Group.objects.filter(
        Q(members=user) | 
        Q(banned_users=user)
    ).values_list('id', flat=True)

    # Combine exclusions with invitations
    excluded_ids = set(excluded_group_ids) | set(invited_group_ids)

    # Filter available groups
    groups = Group.objects.exclude(id__in=excluded_ids)

    # Optional: Search filter
    query = request.GET.get('search', '')
    if query:
        groups = groups.filter(name__icontains=query)

    return render(request, 'freewill/available_groups.html', {
        'available_groups': groups,
    })

@login_required
def leave_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    # Check if the user is a member of the group
    if request.user in group.members.all():
        group.members.remove(request.user)  # Remove the user from the group
        log_event(group, request.user, 'left', f"User left the group")
        messages.success(request, f'You have left the group {group.name}.')
    else:
        messages.error(request, 'You are not a member of this group.') 
    return redirect('freewill:home') 

#----------------------------------------------------- Comments -----------------------------------------------------

@login_required
def communication(request, group_id, edit_comment_id=None):
    group = get_object_or_404(Group, id=group_id)

    # Check membership and role
    if request.user == group.owner:
        user_role = 'owner'
    else:
        try:
            membership = GroupMember.objects.get(group=group, user=request.user)
            user_role = membership.role
        except GroupMember.DoesNotExist:
            messages.error(request, "You are not a member of this group.")
            return redirect('freewill:home')

    # Load comments
    comments = group.comments.select_related('user__profile').order_by('-created_at')
    comment_to_edit = None

    if edit_comment_id:
        comment_to_edit = get_object_or_404(Comment, id=edit_comment_id, group=group)
        if comment_to_edit.user != request.user and user_role not in ['admin', 'owner']:
            messages.error(request, "You don't have permission to edit this comment.")
            return redirect('freewill:communication', group_id=group.id)

    # Handle form POST
    if request.method == 'POST':
        if comment_to_edit:
            old_content = comment_to_edit.content
            form = CommentForm(request.POST, instance=comment_to_edit)
        else:
            form = CommentForm(request.POST)

        if form.is_valid():
            if user_role in ['comment', 'admin', 'owner']:
                comment = form.save(commit=False)
                comment.user = request.user
                comment.group = group
                comment.save()
                if comment_to_edit:
                    log_event(group, request.user, 'comment_edited', f"Edited comment from '{old_content}' to '{comment.content}'")
                else:
                    log_event(group, request.user, 'comment_posted', f"New comment: '{comment.content}'")
                return redirect('freewill:communication', group_id=group.id)
            else:
                messages.error(request, "You don't have permission to comment.")
    else:
        form = CommentForm(instance=comment_to_edit) if comment_to_edit else CommentForm()

    return render(request, 'freewill/communication.html', {
        'group': group,
        'comments': comments,
        'form': form,
        'comment_to_edit': comment_to_edit,
        'user_role': user_role,
    })

@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    group = comment.group
    if (
        comment.user == request.user or
        request.user == comment.group.owner or
        GroupMember.objects.filter(group=comment.group, user=request.user, role='admin').exists()
    ):  # Allow author or group admin to delete
        log_event(group, request.user, 'comment_deleted', f"User deleted comment by {comment.user.username}, '{comment.content}'")
        comment.delete()
    return redirect('freewill:communication', group_id=comment.group.id)

#-------------------------------------------------- Administration --------------------------------------------------

@login_required
def invite_users(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    is_owner = request.user == group.owner
    is_admin = GroupMember.objects.filter(group=group, user=request.user, role='admin').exists()
    is_public = group.visibility == 'public'

    if not (is_owner or is_admin or is_public):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('freewill:group_detail', group_id=group.id)

    invited_user_ids = group.invitations.values_list('invited_user_id', flat=True)
    users_not_in_group = User.objects.exclude(
        id__in=group.members.values_list('id', flat=True)
    ).exclude(
        id__in=group.banned_users.values_list('id', flat=True)
    ).exclude(
        id__in=invited_user_ids
    )

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        invited_user = get_object_or_404(User, id=user_id)

        already_invited = GroupInvitation.objects.filter(group=group, invited_user=invited_user).exists()
        if already_invited:
            messages.info(request, f'{invited_user.profile.nickname} has already been invited.')
        else:
            GroupInvitation.objects.create(
                group=group,
                invited_user=invited_user,
                inviter=request.user
            )
            log_event(group, request.user, 'invited', f"{invited_user.username} was invited to the group")
            messages.success(request, f'Invitation sent to {invited_user.profile.nickname}.')

        return redirect('freewill:group_detail', group_id=group.id)

    outgoing_invitations = GroupInvitation.objects.filter(group=group)

    return render(request, 'freewill/invite_users.html', {
        'group': group,
        'users_not_in_group': users_not_in_group,
        'outgoing_invitations': outgoing_invitations,
        'is_admin': is_admin,
        'is_owner': is_owner,
    })

@login_required
def respond_to_invite(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    user_id = request.GET.get('user_id')
    action = request.GET.get('action')  # 'accept' or 'deny'

    if str(request.user.id) != user_id:
        messages.error(request, "Invalid invitation link.")
        return redirect(request.META.get('HTTP_REFERER', 'freewill:home'))

    if request.user in group.banned_users.all():
        messages.error(request, "You are banned from this group.")
        return redirect(request.META.get('HTTP_REFERER', 'freewill:home'))

    try:
        invitation = GroupInvitation.objects.get(group=group, invited_user=request.user)
    except GroupInvitation.DoesNotExist:
        messages.error(request, "You do not have an active invitation to this group.")
        return redirect(request.META.get('HTTP_REFERER', 'freewill:home'))

    if action == 'accept':
        group.members.add(request.user)
        invitation.delete()
        GroupJoinRequest.objects.filter(group=group, user=request.user).delete()
        log_event(group, request.user, 'invite_accepted', f"User accepted the invite")
        messages.success(request, f'You have successfully joined the group \"{group.name}\".')
    elif action == 'deny':
        invitation.delete()
        log_event(group, request.user, 'invite_denied', f"User denied the invite")
        messages.info(request, f'You have declined the invitation to join \"{group.name}\".')
    else:
        messages.error(request, "Invalid action.")

    return redirect(request.META.get('HTTP_REFERER', 'freewill:home'))

@login_required
def delete_group_invitation(request, group_id, invitation_id):
    group = get_object_or_404(Group, id=group_id)
    invitation = get_object_or_404(GroupInvitation, id=invitation_id, group=group)

    # Check permission: owner or admin
    is_owner = request.user == group.owner
    is_admin = GroupMember.objects.filter(
        group=group, user=request.user, role='admin'
    ).exists()

    if not (is_owner or is_admin):
        messages.error(request, "You do not have permission to delete this invitation.")
        return redirect('freewill:group_detail', group_id=group.id)

    invitation.delete()
    log_event(group, request.user, 'invite_deleted', f"The invite to {invitation.user.username} was deleted")
    messages.success(request, f"Invitation to {invitation.invited_user.username} deleted.")
    return redirect('freewill:group_detail', group_id=group.id)

@login_required
def request_to_join_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    referer = request.META.get('HTTP_REFERER', reverse('freewill:available_groups'))

    if request.user in group.banned_users.all():
        messages.error(request, "You are banned from this group.")
        return redirect(referer)

    if group.visibility != 'invite':
        messages.error(request, "You cannot request to join this group.")
        return redirect(referer)

    if request.user in group.members.all():
        messages.info(request, "You are already a member of this group.")
        return redirect(referer)

    # Proceed to create the join request
    join_request, created = GroupJoinRequest.objects.get_or_create(user=request.user, group=group)
    if created:
        log_event(group, request.user, 'join_requested', "User requested to join the group")
        messages.success(request, "Your request to join the group has been submitted.")
    else:
        messages.info(request, "You have already requested to join this group.")

    return redirect(referer)

@login_required
def delete_join_request(request, request_id):
    join_request = get_object_or_404(GroupJoinRequest, id=request_id, user=request.user)
    group = join_request.group
    # Ensure the logged-in user can only delete their own join requests
    if join_request.user == request.user:
        join_request.delete()
        log_event(group, request.user, 'join_request_deleted', f"User deleted the join request")
        messages.success(request, "Your join request has been successfully deleted.")
    else:
        messages.error(request, "You are not authorised to delete this join request.")
    return redirect('users:user')   

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
        log_event(group, request.user, 'join_request_accepted', f"{join_request.user.username} was accepted")
        join_request.delete()
        GroupInvitation.objects.filter(group=group, invited_user=join_request.user).delete()
        messages.success(request, f"{join_request.user.profile.nickname} has been added to the group.")
    elif action == 'reject':
        log_event(group, request.user, 'join_request_denied', f"{join_request.user.username} was denied")
        join_request.delete()
        messages.info(request, f"{join_request.user.profile.nickname}'s join request has been rejected.")
    else:
        messages.error(request, "Invalid action.")
    
    return redirect('freewill:group_detail', group_id=group.id)

@login_required
def group_logs(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    
    is_admin = GroupMember.objects.filter(group=group, user=request.user, role='admin').exists()
    if request.user != group.owner and not is_admin:
        messages.error(request, "You do not have permission to view this page.")
        return redirect('freewill:group_detail', group_id=group.id)

    logs = group.logs.select_related('user').order_by('-timestamp')

    # Filters
    user_id = request.GET.get('user')
    event_type = request.GET.get('event')
    if user_id:
        logs = logs.filter(user__id=user_id)
    if event_type:
        logs = logs.filter(event_type=event_type)

    return render(request, 'freewill/logs.html', {
        'group': group,
        'logs': logs,
        'users': User.objects.filter(id__in=logs.values_list('user', flat=True).distinct()),
        'event_choices': GroupLog.EVENT_CHOICES,
        'selected_user': user_id,
        'selected_event': event_type,
    })

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
            log_event(group, request.user, 'role_changed', f"User {target_user.username} now has {action} permissions")
            messages.success(request, f"User {target_user.username} now has {action} permissions")
    elif action == 'kick':
        GroupMember.objects.filter(group=group, user=target_user).delete()
        log_event(group, request.user, 'kicked', f"User {target_user.username} was kicked")
        messages.success(request, f"User {target_user.username} was kicked")
    elif action == 'ban':
        GroupMember.objects.filter(group=group, user=target_user).delete()
        group.banned_users.add(target_user)
        log_event(group, request.user, 'banned', f"User {target_user.username} was banned")
        messages.success(request, f"User {target_user.username} was banned")
    else:
        action = request.GET.get('action') or request.POST.get('role')
        if action == 'unban':
            group.banned_users.remove(target_user)
            log_event(group, request.user, 'unbanned', f"User {target_user.username} was unbanned")
            messages.success(request, f"User {target_user.username} was unbanned")
        else:
            messages.error(request, "Invalid action.")

    return redirect('freewill:group_detail', group_id=group.id)

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
            log_event(group, request.user, 'updated', f"Group Updated; Name: {group.name}, Visibility: {group.visibility}, Default Permissions: {group.default_role}")
            messages.success(request, 'Group settings updated.')
            return redirect('freewill:group_detail', group_id=group.id)
    else:
        form = GroupCreationForm(instance=group, user=request.user)

    return render(request, 'freewill/settings.html', {'form': form, 'group': group})

@login_required
def transfer_ownership(request, group_id):
    group = get_object_or_404(Group, id=group_id)

    if request.user != group.owner:
        return redirect('freewill:group_detail', group_id=group.id)

    admin_members = GroupMember.objects.filter(group=group, role='admin').exclude(user=group.owner)

    if request.method == 'POST':
        new_owner_id = request.POST.get('new_owner_id')
        password = request.POST.get('password')

        # Authenticate the current user with password
        user = authenticate(username=request.user.username, password=password)
        if not user:
            messages.error(request, "Password incorrect. Ownership not transferred.")
            return redirect('freewill:transfer_ownership', group_id=group.id)

        try:
            new_owner = User.objects.get(id=new_owner_id)

            if not admin_members.filter(user=new_owner).exists():
                messages.error(request, "Selected user must be an admin.")
                return redirect('freewill:transfer_ownership', group_id=group.id)

            # Transfer ownership
            group.owner = new_owner
            group.save()

            # Downgrade the old owner to 'admin'
            old_owner_membership, _ = GroupMember.objects.get_or_create(user=request.user, group=group)
            old_owner_membership.role = 'admin'
            old_owner_membership.save()

            # Set new owner role
            try:
                new_owner_membership = GroupMember.objects.get(user=new_owner, group=group)
                new_owner_membership.role = 'owner'
                new_owner_membership.save()
            except GroupMember.DoesNotExist:
                GroupMember.objects.create(user=new_owner, group=group, role='owner')

            log_event(group, request.user, 'ownership_transferred', f"Transferred ownership to {new_owner.username}")
            send_transfer_ownership_email(user, request, group)
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

    if request.user != group.owner:
        messages.error(request, "Only the owner can delete this group.")
        return redirect('freewill:group_detail', group_id=group.id)

    if request.method == 'POST':
        password = request.POST.get('password')
        user = authenticate(username=request.user.username, password=password)
        if user:
            group.delete()
            messages.success(request, "Group deleted successfully.")
            send_delete_group_email(user, request, group)
            return redirect('freewill:home')
        else:
            messages.error(request, "Password incorrect. Group was not deleted.")

    return render(request, 'freewill/delete_group.html', {
        'group': group,
    })