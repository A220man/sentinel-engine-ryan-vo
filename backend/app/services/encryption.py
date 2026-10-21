from cryptography.fernet import Fernet
from app.core.config import settings
import base64
import os


class EncryptionService:
    def __init__(self):
        key = settings.encryption_key
        if not key:
            # Generate a key from a seed for demo; in production, use a proper key
            seed = b"sentinel-engine-demo-key-seed-32bytes!!"
            key = base64.urlsafe_b64encode(seed[:32].ljust(32, b'0'))
        elif len(key) != 44:  # Fernet key is 32 bytes base64 encoded = 44 chars
            # Derive from provided key
            key = base64.urlsafe_b64encode(key.encode()[:32].ljust(32, b'0'))
        self.fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        try:
            return self.fernet.decrypt(ciphertext.encode()).decode()
        except Exception:
            return ""


encryption_service = EncryptionService()