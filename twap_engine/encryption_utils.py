from cryptography.fernet import Fernet
import json
import os

KEY_FILE = "secret.key"

def generate_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, "wb") as f:
            f.write(key)
def load_key():
    with open(KEY_FILE, "rb") as f:
        return f.read()

def encrypt_data(data: dict) -> bytes:
    fernet = Fernet(load_key())
    return fernet.encrypt(json.dumps(data).encode())

def decrypt_data(token: bytes) -> dict:
    fernet = Fernet(load_key())
    return json.loads(fernet.decrypt(token).decode())
