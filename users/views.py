from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserRegistrationForm
import requests
from django.conf import settings

# Registers user

def register(request):
    if request.user.is_authenticated:
        return redirect('users:user')
    else:
        if request.method == "POST":
            form = UserRegistrationForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Please verify your account through the email sent")
                return redirect('users:login')
        else:
            form = UserRegistrationForm()
        return render(request, 'users/register.html', {'form': form})

@login_required(login_url='users:login')
def user(request):
    return render(request, "users/user.html")

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
                return redirect('users:send_login_email')
            else:
                messages.error(request, "Invalid username or password.")
        return render(request, "users/login.html")

# Logs user out

def logout_view(request):
    logout(request)
    messages.success(request, "Successfully logged out.")
    return redirect('users:login')


#----------------------------------------------- CHIP IN --------------------------------------------------------

# Send login email

@login_required
def send_login_email(request):
    user = request.user
    subject = 'Logged into LF Project!'
    message = (

        f"Hi {user.username},\n\n"
        f"You recently logged into your account.\n\n"
        f"If you don't recognise this action, change your password and contact support immediately.\n\n"
        f"Regards,\nLF Project"

    )

    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
    # Redirect to the next URL if provided, else default to user profile
    next_url = request.GET.get('next', reverse("users:user"))  # Simplified fallback
    return redirect(next_url)

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.http import HttpResponse

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
        messages.success(request, "Your email has been confirmed.")
        return redirect('users:send_confirmation_success_email')
    else:
        messages.success(request, "The confirmation link is invalid or has expired.")
        return redirect('users:login')

# Confirm email verification

@login_required
def send_confirmation_success_email(request):
    user = request.user
    subject = 'Welcome to LF Project!'

    message =(

        f"Hi {user.username},\n\n"
        f"Your email has been successfully verified and your account is now active.\n\n"
        f"Regards,\nLF Project"

    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
    return redirect('users:user')

# Delete account

from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from django.core.mail import send_mail
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.conf import settings
from django.contrib import messages


signer = TimestampSigner()

@login_required
def delete_account(request):
    if request.method == "POST":
        password = request.POST.get('password') # Verify deletion with password
        user = request.user
        user = authenticate(username=user.username, password=password) # Authenticate password
        if user is not None:
            token = signer.sign(str(user.id))
            confirm_url = request.build_absolute_uri(
                reverse('users:confirm_delete_account') + f'?token={token}'
            )
            send_mail(
                subject='Confirm Your Account Deletion',
                message=(

                    f"Hi {user.username},\n\n"
                    f"Click the link below to confirm deletion of your account:\n\n"
                    f"{confirm_url}\n\n"
                    f"If you don't recognise this action, change your password and contact support immediately.\n\n"
                    f"Regards,\nLF Project"

                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            messages.info(request, "A confirmation email has been sent to your email address.")
            return redirect('users:login')
        else:
            messages.error(request, "Incorrect password. Please try again.")
    return render(request, 'users/delete_account.html')

signer = TimestampSigner()

def confirm_delete_account(request):
    token = request.GET.get('token')
    try:
        user_id = signer.unsign(token, max_age=60 * 60)  # token valid for 1 hour
        user = User.objects.get(id=user_id)
        send_mail(
            subject='Account Deletion Confirmation',
            message=(

                f"Hi {user.username},\n\n"
                f"Your account has been successfully deleted.\n\n"
                f"If you don't recognise this action, change your password and contact support immediately.\n\n"
                f"Regards,\nLF Project"

            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        user.delete()
        logout(request)
        messages.success(request, "Your account has been deleted.")
        return redirect('users:login')
    except (BadSignature, SignatureExpired, User.DoesNotExist):
        messages.error(request, "Invalid or expired link.")
        return redirect('users:login')