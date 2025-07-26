from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)  # Safely create the profile without duplicating

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):  # Ensure profile exists before trying to save
        instance.profile.save()

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nickname = models.CharField(max_length=30, unique=False, null=False, blank=False) # No need to be unique
    pending_email = models.EmailField(blank=True, null=True) # For changing email, saves the new email seperately until its saved

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)    

    def __str__(self):
        return self.user.username