import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
load_dotenv(BASE_DIR.parent / '.env', override=False)

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-only-change-me')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if host.strip()]

INSTALLED_APPS = ['django.contrib.contenttypes', 'django.contrib.auth', 'corsheaders', 'rest_framework', 'api']
MIDDLEWARE = ['corsheaders.middleware.CorsMiddleware', 'django.middleware.security.SecurityMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.middleware.common.CommonMiddleware', 'api.middleware.EventBannerUploadMiddleware']
ROOT_URLCONF = 'alumni_project.urls'
TEMPLATES = []
WSGI_APPLICATION = 'alumni_project.wsgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
TIME_ZONE = 'Asia/Kolkata'
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',') if origin.strip()]
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '25'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False').lower() == 'true'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'webmaster@localhost')
OTP_EXPIRY_SECONDS = int(os.getenv('OTP_EXPIRY_SECONDS', '300'))
OTP_LENGTH = int(os.getenv('OTP_LENGTH', '6'))
OTP_MAX_ATTEMPTS = int(os.getenv('OTP_MAX_ATTEMPTS', '5'))
JWT_ACCESS_MINUTES = int(os.getenv('JWT_ACCESS_MINUTES', str(int(os.getenv('SIMPLE_JWT_ACCESS_TOKEN_LIFETIME_SECONDS', '3600')) // 60)))
JWT_REFRESH_MINUTES = int(os.getenv('JWT_REFRESH_MINUTES', str(int(os.getenv('SIMPLE_JWT_REFRESH_TOKEN_LIFETIME_SECONDS', '604800')) // 60)))
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES': ['api.authentication.CookieJWTAuthentication'], 'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'], 'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'], 'DEFAULT_THROTTLE_RATES': {'login': '5/minute', 'register': '3/minute', 'password_reset': '10/minute', 'user_actions': '30/minute'}}
MONGODB_URI = os.getenv('MONGODB_URI', '')
MONGODB_NAME = os.getenv('MONGODB_NAME', 'alumni_meet')
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'
