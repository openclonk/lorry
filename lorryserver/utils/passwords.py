import hmac
import hashlib
import passlib.context
import secrets

password_context = passlib.context.CryptContext(
	schemes=["pbkdf2_sha256"],
	default="pbkdf2_sha256",
	pbkdf2_sha256__default_rounds=30000
)

def hash_password(password):
	return password_context.encrypt(password)

def check_hashed_password(password, hashed):
	return password_context.verify(password, hashed)

def generate_nonce():
	return secrets.token_urlsafe()

def generate_sso_payload_signature(payload, secret_key):
    signature = hmac.new(secret_key, msg=payload, digestmod=hashlib.sha256).hexdigest()
    return signature