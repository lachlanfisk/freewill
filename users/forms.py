from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username', 'password1', 'password2']

    # Only allows unique emails

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    # Saves the user until verified

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.is_active = False
        if commit:
            user.save()
            profile = user.profile
            profile.nickname = user.username
            profile.save()

            # Sends user verification email

            self.send_confirmation_email(user)
        return user

    def send_confirmation_email(self, user):
        from django.urls import reverse

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        link = f"http://localhost:8000/users/verify-email/{uid}/{token}/"

        subject = 'Confirm your email address'
        message =(

            f"Hi {user.username},\n\n"
            f"Thanks for registering! Please confirm your email address by clicking the link below:\n\n"
            f"{link}\n\n"
            f"Regards,\nLF Project"

        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])