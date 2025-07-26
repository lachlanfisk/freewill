from django import forms
from .models import Group, Comment, GroupMember

class GroupCreationForm(forms.ModelForm):
    DEFAULT_ROLE_CHOICES = [
        ('read', 'Read-Only'),
        ('comment', 'Comment'),
    ]
    default_role = forms.ChoiceField(choices=DEFAULT_ROLE_CHOICES, label="Default Role for Members") # Default Role

    class Meta:
        model = Group
        fields = ['name', 'nickname', 'visibility']  # Group Settings

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def save(self, commit=True):
        group = super().save(commit=False)
        is_new = group.pk is None

        # Sets creation user as owner
        group.owner = self.user
        if commit:
            group.save()
            if is_new:
                GroupMember.objects.create(user=self.user, group=group, role='owner')
        return group


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter your comment...'})
        }

    # Clean the content to sanitise input
    def clean_content(self):
        content = self.cleaned_data.get('content')
        if "<script>" in content.lower():  # Prevent XSS by checking for script tags
            raise forms.ValidationError("Invalid content.")
        return content