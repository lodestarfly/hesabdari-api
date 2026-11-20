# در Python اجرا کنید:
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())
# خروجی را در ENCRYPTION_KEY قرار دهید