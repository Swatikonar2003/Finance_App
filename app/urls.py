from django.urls import path
from .views import (
    UserView,
    SignupView,
    LoginView,
    RequestOTPView,
    VerifyOTPView,
    ForgetPasswordView,  # Import ForgetPasswordView
    ResetPasswordView    # Import ResetPasswordView
)

urlpatterns = [
    path('user/', UserView.as_view(), name='user_detail'),
    # URL pattern for user signup
    path('signup/', SignupView.as_view(), name='signup'),
    # URL pattern for user login
    path('login/', LoginView.as_view(), name='login'),
    # URL pattern for email verification (sent via the signup process)
    path('request-otp/', RequestOTPView.as_view(), name='request_otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify_otp'),
    # URL pattern for forget password (request password reset)
    path('forget-password/', ForgetPasswordView.as_view(), name='forget_password'),  # New path for forget password
    # URL pattern for password reset (reset password with token)
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),    # New path for password reset
]
