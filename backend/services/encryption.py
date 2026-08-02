import base64
import hashlib
from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet() -> Fernet:
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(text: str) -> str:
    return _get_fernet().encrypt(text.encode()).decode()


def decrypt(text: str) -> str:
    return _get_fernet().decrypt(text.encode()).decode()
