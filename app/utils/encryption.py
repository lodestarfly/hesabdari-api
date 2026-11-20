from cryptography.fernet import Fernet
from app.core.config import settings
import base64

class EncryptionService:
    def __init__(self):
        # تبدیل کلید به فرمت مناسب
        key = settings.ENCRYPTION_KEY
        if not key:
            raise ValueError("ENCRYPTION_KEY is not set")
        
        # اگر کلید base64 نیست، آن را تبدیل کن
        try:
            base64.urlsafe_b64decode(key)
            self.cipher = Fernet(key.encode())
        except:
            # اگر کلید raw است، آن را به base64 تبدیل کن
            key_bytes = key.encode()[:32].ljust(32, b'\0')
            encoded_key = base64.urlsafe_b64encode(key_bytes)
            self.cipher = Fernet(encoded_key)
    
    def encrypt(self, data: str) -> str:
        """رمزنگاری داده"""
        if not data:
            return ""
        encrypted = self.cipher.encrypt(data.encode())
        return encrypted.decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """رمزگشایی داده"""
        if not encrypted_data:
            return ""
        decrypted = self.cipher.decrypt(encrypted_data.encode())
        return decrypted.decode()

encryption_service = EncryptionService()