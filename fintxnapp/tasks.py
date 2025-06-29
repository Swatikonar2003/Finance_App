from celery import shared_task
from .ai_core.csv_parser import process_csv_and_extract
from django.contrib.auth import get_user_model
import io
import base64    # provides functions for encoding and decoding data using Base64.
from django.core.cache import cache    # object provides a simple interface for interacting with the configured cache backend (e.g., Redis, Memcached, in-memory cache).

User = get_user_model()

@shared_task
def process_csv_file_task(file_base64, user_id, save_to_db):
    try:
        user = User.objects.get(id=user_id)
        # This line decodes the base64 encoded string (file_base64) back into its original binary format (bytes).
        decoded = base64.b64decode(file_base64)
        #  creates an in-memory binary stream using io.BytesIO. It wraps the decoded binary data, allowing to treat the CSV data as a file-like object.
        file_like = io.BytesIO(decoded)
        result = process_csv_and_extract(file_like, user, save_to_db)
        # This line stores the result (the processed data) in Django's cache.
        cache.set(f"csv_result_{user_id}", result, timeout=3600)  #After this time, the data will be automatically removed from the cache.
        return {"status": "success"}
    except Exception as e:
        # this line stores an error message in the cache under the same user-specific key. This allows the AICSVResultView to retrieve and display the error to the user
        cache.set(f"csv_result_{user_id}", {"error": str(e)}, timeout=3600)
        return {"status": "failed", "error": str(e)}
