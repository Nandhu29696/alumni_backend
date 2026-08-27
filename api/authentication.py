from rest_framework import authentication, exceptions
from .repository import find_user
from .tokens import decode_token


class MongoUser(dict):
    @property
    def pk(self):
        return self.get('id')

    @property
    def is_authenticated(self):
        return True


class CookieJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        raw_token = request.COOKIES.get('access_token')
        if not raw_token:
            header = request.headers.get('Authorization', '')
            raw_token = header[7:] if header.startswith('Bearer ') else None
        if not raw_token:
            return None
        try:
            payload = decode_token(raw_token, 'access')
        except ValueError as error:
            raise exceptions.AuthenticationFailed(str(error)) from error
        user = find_user(payload['sub'])
        if not user:
            raise exceptions.AuthenticationFailed('User not found.')
        user = MongoUser(user)
        user['id'] = str(user['_id'])
        return user, payload

    def authenticate_header(self, request):
        return 'Bearer'
