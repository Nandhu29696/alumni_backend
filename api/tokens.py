from datetime import datetime, timedelta, timezone
import jwt
from django.conf import settings


def create_token(user_id, token_type, minutes):
    return jwt.encode({'sub': str(user_id), 'type': token_type, 'exp': datetime.now(timezone.utc) + timedelta(minutes=minutes)}, settings.SECRET_KEY, algorithm='HS256')


def decode_token(token, expected_type):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
    except jwt.PyJWTError as error:
        raise ValueError('Invalid or expired token.') from error
    if payload.get('type') != expected_type:
        raise ValueError('Invalid token type.')
    return payload
