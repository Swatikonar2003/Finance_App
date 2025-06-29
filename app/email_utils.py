from django.core.mail import send_mail
from django.conf import settings
import logging

# Configure logging to track email sending errors
logger = logging.getLogger(__name__)

def send_email(subject, message, to_email):
    """
    Sends an email with the given subject, message, and recipient email.

    Args:
        subject (str): The subject of the email.
        message (str): The body message of the email.
        to_email (str): The recipient's email address.
    """
    from_email = settings.DEFAULT_FROM_EMAIL  # Ensure DEFAULT_FROM_EMAIL is set correctly in settings
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[to_email],
            fail_silently=False  # Set to False to raise exceptions on errors
        )
        logger.info(f"Email sent successfully to {to_email}")
    except Exception as e:
        # Log the error for debugging purposes
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        raise Exception("There was an error sending the email.")
