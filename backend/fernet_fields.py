from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


class EncryptedCharField(models.CharField):
    """
    A simple CharField that uses cryptography.fernet to encrypt data.
    Provides transparent read/write, and falls back to plaintext if the
    data is not valid Fernet ciphertext (useful for data migrations).
    """

    def get_fernet(self):
        keys = getattr(settings, "FERNET_KEYS", [])
        if not keys or not keys[0]:
            # For makemigrations without a key set
            return Fernet(Fernet.generate_key())
        return Fernet(keys[0])

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        return self.get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return self.get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            # Fallback to plaintext if decryption fails
            return value
