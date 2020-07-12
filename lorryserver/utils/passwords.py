import hmac
import hashlib
import secrets

def generate_nonce():
	return secrets.token_urlsafe()

def generate_sso_payload_signature(payload, secret_key):
    signature = hmac.new(secret_key.encode(), msg=payload, digestmod=hashlib.sha256).hexdigest()
    return signature

def verify_sso_response_signature(response, signature, secret_key):
	sig = generate_sso_payload_signature(response, secret_key)
	return signature == sig
