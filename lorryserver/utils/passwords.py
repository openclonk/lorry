import passlib.context

password_context = passlib.context.CryptContext(
	schemes=["pbkdf2_sha256"],
	default="pbkdf2_sha256",
	pbkdf2_sha256__default_rounds=30000
)

def hash_password(password):
	return password_context.encrypt(password)


def check_hashed_password(password, hashed):
	return password_context.verify(password, hashed)
