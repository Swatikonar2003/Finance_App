from django.shortcuts import render
import random
from django.utils import timezone
from datetime import timedelta

# Import necessary modules and classes for API views and functionality
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.contrib.auth import authenticate, get_user_model
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.core.exceptions import ObjectDoesNotExist

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CustomUser, EmailOTP
from .email_utils import send_email
from .serializers import UserSerializer

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

# Get the user model dynamically to support custom user models
User = get_user_model()

from rest_framework_simplejwt.tokens import AccessToken
from django.shortcuts import get_object_or_404


class UserView(APIView):
    """
    Returns the details of the currently authenticated user.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class RequestOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Check if the user already exists
        if User.objects.filter(email=email).exists():
            return Response({"error": "Email is already registered."}, status=status.HTTP_400_BAD_REQUEST)

        otp = f"{random.randint(100000, 999999)}"
        EmailOTP.objects.update_or_create(email=email, defaults={'otp': otp, 'is_verified': False})

        send_email(
            subject="Your OTP Code",
            message=f"Your verification OTP is {otp}",
            to_email=email
        )

        return Response({"message": "OTP sent to your email."}, status=status.HTTP_200_OK)
    

# View for verifying user email
class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')

        try:
            record = EmailOTP.objects.get(email=email)
        except EmailOTP.DoesNotExist:
            return Response({"error": "OTP not requested for this email."}, status=status.HTTP_400_BAD_REQUEST)

        if record.otp != otp:
            return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        record.is_verified = True
        record.save()

        return Response({"message": "Email verified successfully."}, status=status.HTTP_200_OK)


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        username = request.data.get('username')
        password = request.data.get('password')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')

        try:
            otp_record = EmailOTP.objects.get(email=email)
            if not otp_record.is_verified:
                return Response({"error": "Email not verified."}, status=status.HTTP_400_BAD_REQUEST)
        except EmailOTP.DoesNotExist:
            return Response({"error": "Email not verified."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({"error": "Email already registered."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already in use."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_verified=True,
            is_active=True
        )

        # Clean up OTP record
        otp_record.delete()

        return Response({"message": "Signup successful."}, status=status.HTTP_201_CREATED)
        

# View for user login and token generation
class LoginView(APIView):
    """
    This view handles user authentication and token generation.
    Upon successful login, the user receives both access and refresh tokens.
    """
    permission_classes = [AllowAny]  # Allow access to unauthenticated users

    @swagger_auto_schema(
        operation_description="Authenticate a user and return a JWT token along with user details.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='User username'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='User password'),
            },
            required=['username', 'password']
        ),
        responses={
            200: openapi.Response('Successful login', schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'refresh': openapi.Schema(type=openapi.TYPE_STRING, description='Refresh token'),
                    'access': openapi.Schema(type=openapi.TYPE_STRING, description='Access token'),
                    'user': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID'),
                            'username': openapi.Schema(type=openapi.TYPE_STRING, description='Username'),
                            'email': openapi.Schema(type=openapi.TYPE_STRING, description='Email'),
                        }
                    ),
                }
            )),
            401: openapi.Response('Invalid credentials'),
            403: openapi.Response('Account not verified'),
        }
    )
    def post(self, request):
        """
        Authenticate the user with email and password. If valid credentials are provided,
        return JWT tokens and user details.
        """
        username = request.data.get('username')  # Get email from request data
        password = request.data.get('password')  # Get password from request data

        # Authenticate the user using provided credentials
        user = authenticate(request, username=username, password=password)

        if user is None:
            # Return error if authentication fails
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_verified:
            return Response({"error": "Account not verified. Please check your email."}, status=status.HTTP_403_FORBIDDEN)

        # Generate JWT tokens for the authenticated user
        token = RefreshToken.for_user(user)
        return Response({
            "refresh": str(token),
            "access": str(token.access_token),
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name
            }
        })


class ForgetPasswordView(APIView):
    """
    This view handles the forget password functionality. The user enters their email address,
    and a reset password link is sent to their email. This link contains a token to reset their password.
    """
    permission_classes = [AllowAny]  # Allow access to unauthenticated users

    @swagger_auto_schema(
        operation_description="Request password reset by providing the email address.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, description='User email'),
            },
            required=['email']
        ),
        responses={
            200: openapi.Response('Password reset email sent'),
            400: openapi.Response('Email not registered'),
        }
    )
    def post(self, request):
        email = request.data.get('email')  # Get email from request data

        try:
            # Check if the email exists in the system
            user = User.objects.get(email=email)
        except ObjectDoesNotExist:
            return Response({"error": "Email not registered"}, status=status.HTTP_400_BAD_REQUEST)

        # Generate a token for password reset (you can use a random string or JWT)
        reset_token = get_random_string(length=32)

        # Save the token for future validation (store it in a password reset model or user model)
        user.password_reset_token = reset_token  # You may need to add this field to the user model
        user.save()

        # Create the reset password URL
        reset_link = request.build_absolute_uri(reverse('reset_password')) + f"?token={reset_token}"

        # Send the reset link via email using the imported send_email function
        send_email(
            subject="Password Reset Request",
            message=f"Click the link to reset your password: {reset_link}",
            to_email=email
        )

        return Response({"message": "Password reset email sent. Please check your inbox."}, status=status.HTTP_200_OK)
    

class ResetPasswordView(APIView):
    """
    This view allows the user to reset their password using the token sent in the reset email.
    """
    permission_classes = [AllowAny]  # Allow access to unauthenticated users

    @swagger_auto_schema(
        operation_description="Reset password using the provided reset token.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'token': openapi.Schema(type=openapi.TYPE_STRING, description='Reset token'),
                'new_password': openapi.Schema(type=openapi.TYPE_STRING, description='New password'),
            },
            required=['token', 'new_password']
        ),
        responses={
            200: openapi.Response('Password successfully reset'),
            400: openapi.Response('Invalid or expired token'),
        }
    )
    def post(self, request):
        token = request.data.get('token')  # Get the reset token from request data
        new_password = request.data.get('new_password')  # Get the new password

        # Verify the token and find the user associated with it
        try:
            user = User.objects.get(password_reset_token=token)
        except ObjectDoesNotExist:
            return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)

        # Reset the user's password
        user.set_password(new_password)
        user.password_reset_token = None  # Clear the reset token after use
        user.save()

        return Response({"message": "Password successfully reset."}, status=status.HTTP_200_OK)
