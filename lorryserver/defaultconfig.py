DEBUG = False
SECRET_KEY = b'fillmewithdata'
SQLALCHEMY_DATABASE_URI = "postgres://user:password@localhost:5432/databasename"
SQLALCHEMY_TRACK_MODIFICATIONS = False

OWN_HOST = "localhost"
RESOURCES_PATH = "/some/local/path/"
TEST_DATA_PATH = "/some/local/path/containing/at/least/three/testfiles/"

DEBUG = False
SECRET_KEY = b'fillmewithdata'
SESSION_COOKIE_SAMESITE = "Lax"

SQLALCHEMY_DATABASE_URI = "postgres://user:password@localhost:5432/databasename"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Note that the simple in-memory cache is not shared between worker threads.
# That means that different connections to the website might yield different cache states.
# So we combine that with a short cache timeout.
CACHE_TYPE = "simple"
CACHE_DEFAULT_TIMEOUT = 60

OWN_HOST = "localhost"
RESOURCES_PATH = "/some/local/path/"
TEST_DATA_PATH = "/some/local/path/containing/at/least/three/testfiles/"
ALLOWED_FILE_EXTENSIONS = ("ocs", "ocf", "ocd")

#SSO_ENDPOINT = "https://example.com/"
SSO_ENDPOINT = None

SSO_HMAC_SECRET = "some secret"
