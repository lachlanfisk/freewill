from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile

class UserRegistrationForm(UserCreationForm):
    nickname = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ['username', 'password1', 'password2', 'nickname']

    def save(self, commit=True):
        user = super().save(commit=False)       
        if commit:
            user.save()
            profile = user.profile
            profile.nickname = self.cleaned_data['nickname']
            profile.save()
        return user