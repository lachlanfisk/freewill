from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.signing import SignatureExpired, BadSignature
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_decode
from .forms import UserRegistrationForm, UserUpdateForm, ProfileUpdateForm, EmailChangeForm
from .utils import (
    send_confirmation_email,
    send_confirmation_success_email,
    send_login_email,
    send_profile_update_email,
    send_email_change_email,
    send_email_change_success_email,
    send_password_change_email,
    send_delete_account_email,
    send_delete_account_success_email
)
from freewill.models import GroupJoinRequest
import requests

# Registers user

def register(request):
    if request.user.is_authenticated:
        return redirect('users:user')
    else:
        if request.method == "POST":
            form = UserRegistrationForm(request.POST)
            if form.is_valid():
                user = form.save()
                send_confirmation_email(user)
                messages.success(request, "Please verify your account through the email sent")
                return redirect('users:login')
        else:
            form = UserRegistrationForm()
        return render(request, 'users/register.html', {'form': form})

# Verify user's email

def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        send_confirmation_success_email(user)
        messages.success(request, "Your email has been confirmed.")
        return redirect('users:user')
    else:
        messages.success(request, "The confirmation link is invalid or has expired.")
        return redirect('users:login')

# Logs user in

def login_view(request):
    if request.user.is_authenticated:
        return redirect('users:user')
    else:
        if request.method == "POST":
            username = request.POST.get("username")
            password = request.POST.get("password")
            recaptcha_response = request.POST.get("recaptcha-token")  # Updated
            # Verify reCAPTCHA
            data = {
                'secret': settings.RECAPTCHA_SECRET_KEY,
                'response': recaptcha_response,
                'remoteip': request.META.get('REMOTE_ADDR'),
            }
            recaptcha_verification = requests.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data=data
            )
            result = recaptcha_verification.json()
            # Check reCAPTCHA response
            if not result.get("success"):
                messages.error(request, "reCAPTCHA validation failed. Please try again.")
                return redirect("users:login")  # Redirect back to the login page
            # Authenticate user if reCAPTCHA is valid
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                send_login_email(user, request)
                # Redirect to the next URL if provided, else default to user profile
                next_url = request.GET.get('next', reverse("users:user"))  # Simplified fallback
                return redirect(next_url)

            else:
                messages.error(request, "Invalid username or password.")
        return render(request, "users/login.html")

# Account page

@login_required
def user(request):
    user = request.user
    profile = user.profile

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=user)
        profile_form = ProfileUpdateForm(request.POST, instance=profile)
        password_form = PasswordChangeForm(user, request.POST)
        email_form = EmailChangeForm(request.POST)  # New form, not bound to user

        # Original data before saving anything
        original_data = {
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'nickname': profile.nickname,
            'email': user.email,  # For comparison only
        }

        # --- Handle profile updates ---
        if 'update_profile' in request.POST and user_form.is_valid() and profile_form.is_valid():
            user_form.cleaned_data.pop('email', None)  # Don't accidentally save email

            user_form.save()
            profile_form.save()

            user.refresh_from_db()
            profile.refresh_from_db()

            updated_data = {
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'nickname': profile.nickname,
            }

            changes = {}
            for field in updated_data:
                old = (original_data[field] or '').strip()
                new = (updated_data[field] or '').strip()
                if old != new:
                    changes[field] = (old, new)

            if changes:
                send_profile_update_email(user, request, changes)
            messages.success(request, 'Profile updated successfully.')
            return redirect('users:user')

        # --- Handle password change ---
        elif 'change_password' in request.POST and password_form.is_valid():
            user = password_form.save()
            update_session_auth_hash(request, user)
            send_password_change_email(user, request)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('users:user')

        # --- Handle email change request ---
        elif 'change_email' in request.POST and email_form.is_valid():
            new_email = email_form.cleaned_data['new_email']
            if new_email != original_data['email']:
                profile.pending_email = new_email
                profile.save()
                send_email_change_email(user, request, new_email)
                messages.success(request, "A confirmation link has been sent to your new email.")
                return redirect('users:user')
            else:
                messages.info(request, "You entered the same email as your current one.")

    else:
        user_form = UserUpdateForm(instance=user)
        profile_form = ProfileUpdateForm(instance=profile)
        password_form = PasswordChangeForm(user)
        email_form = EmailChangeForm()

    # Get join requests
    user_join_requests = GroupJoinRequest.objects.filter(user=user)
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
        'email_form': email_form,
        'created_at': user.date_joined,
        'user_join_requests': user_join_requests,
    }
    return render(request, 'users/user.html', context)

# Logs user out

def logout_view(request):
    logout(request)
    messages.success(request, "Successfully logged out.")
    return redirect('users:login')

# Confirm email change

def confirm_email_change(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError):
        user = None

    if user and default_token_generator.check_token(user, token):
        profile = user.profile
        if profile.pending_email:
            new_email = profile.pending_email
            send_email_change_success_email(user, request, new_email)
            user.email = profile.pending_email
            user.save()
            profile.pending_email = None
            profile.save()
            messages.success(request, "Your email address has been updated.")
        else:
            messages.error(request, "No pending email found.")
    else:
        messages.error(request, "Invalid or expired confirmation link.")

    return redirect('users:user')

# Change Password

@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Prevent logout
            messages.success(request, "Your password has been changed successfully.")
            return redirect('users:user')  # or wherever you want to redirect after
    else:
        form = PasswordChangeForm(user=request.user)
    
    return render(request, 'users/change_password.html', {'form': form})

# Delete account request

@login_required
def delete_account(request):
    if request.method == "POST":
        password = request.POST.get('password') # Verify deletion with password
        user = request.user
        user = authenticate(username=user.username, password=password) # Authenticate password
        if user is not None:
            send_delete_account_email(user, request)
            messages.info(request, "A confirmation email has been sent to your email address.")
            return redirect('users:login')
        else:
            messages.error(request, "Incorrect password. Please try again.")
    return render(request, 'users/delete_account.html')

# Confirm account deletion

def confirm_delete_account(request):
    user = request.user
    token = request.GET.get('token')
    try:
        send_delete_account_success_email(token, request)
        user.delete()
        logout(request)
        messages.success(request, "Your account has been deleted.")
        return redirect('users:login')
    except (BadSignature, SignatureExpired, User.DoesNotExist):
        messages.error(request, "Invalid or expired link.")
        return redirect('users:login')

