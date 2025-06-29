from django.contrib.auth.models import AbstractUser
from django.db import models


# Custom User model with additional fields
# Inherits from AbstractUser and adds a boolean field for email verification status
class CustomUser(AbstractUser):
    # This field indicates if the user's email has been verified
    is_verified = models.BooleanField(default=False)
    password_reset_token = models.CharField(max_length=32, blank=True, null=True)

    def __str__(self):
        return self.username  # Returns the username when the user object is printed
    

class EmailOTP(models.Model):
    email = models.EmailField(unique=True)
    otp = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email