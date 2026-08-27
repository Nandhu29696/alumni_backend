import base64
import csv
import io
import secrets
from django.core.mail import send_mail
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, quote, urlparse
from decimal import Decimal
from bson import ObjectId
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import HttpResponse

from .authentication import CookieJWTAuthentication
from .permissions import IsAdmin
from .repository import get_alumni, get_database, get_event, get_events, get_role, get_role_by_id, normalize_event, now, serialize
from .serializers import AdminEventSerializer, AdminPersonSerializer, ChangePasswordSerializer, CheckInSerializer, EventSerializer, ForgotPasswordSerializer, LoginSerializer, ProfileSerializer, RegisterSerializer, ResetPasswordSerializer, RSVPSerializer
from .throttles import LoginRateThrottle, PasswordResetRateThrottle, RegisterRateThrottle, UserActionRateThrottle
from .tokens import create_token, decode_token


def set_auth_cookies(response, user_id):
    response.set_cookie('access_token', create_token(user_id, 'access', settings.JWT_ACCESS_MINUTES), httponly=True, secure=not settings.DEBUG, samesite='Lax', max_age=settings.JWT_ACCESS_MINUTES * 60)
    response.set_cookie('refresh_token', create_token(user_id, 'refresh', settings.JWT_REFRESH_MINUTES), httponly=True, secure=not settings.DEBUG, samesite='Lax', max_age=settings.JWT_REFRESH_MINUTES * 60)


def mongo_safe(data):
    return {key: float(value) if isinstance(value, Decimal) else value for key, value in data.items()}


def registration_qr(token):
    import qrcode

    image = qrcode.make(registration_url(token))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def registration_url(token):
    return f'{settings.FRONTEND_URL.rstrip("/")}/check-in?token={quote(token)}'


def registration_token(value):
    parsed = urlparse(value)
    if parsed.query:
        return parse_qs(parsed.query).get('token', [value])[0]
    return value


def make_otp():
    return ''.join(str(secrets.randbelow(10)) for _ in range(settings.OTP_LENGTH))


PROFILE_FIELDS = ('batch_year', 'current_company', 'job_title', 'location', 'bio', 'avatar_image', 'cover_image', 'phone_country_code', 'phone_number', 'address', 'country', 'pincode')


def otp_expired(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= now()


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'status': 'ok', 'service': 'alumni-meet-api'})


class CSRFView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'csrfToken': get_token(request)})


class EventBannerUploadView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdmin]
    parser_classes = [MultiPartParser]

    def post(self, request):
        banner_url = getattr(request, 'uploaded_banner_url', None)
        if not banner_url:
            return Response({'detail': 'Banner upload could not be processed.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'banner_image': banner_url}, status=status.HTTP_201_CREATED)


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        database = get_database()
        users = database.users
        if users.find_one({'email': data['email'].lower()}):
            return Response({'detail': 'An account with this email already exists.'}, status=status.HTTP_409_CONFLICT)
        requested_role = get_role_by_id(database, data.pop('role_id', '')) if data.get('role_id') else get_role(database)
        if not requested_role or requested_role['code'] == 'super_admin':
            return Response({'detail': 'Registration is limited to alumni or student roles.'}, status=status.HTTP_400_BAD_REQUEST)
        user = {**data, 'email': data['email'].lower(), 'password': make_password(data['password']), 'role_id': requested_role['_id'], 'role': requested_role['code'], **{field: None for field in PROFILE_FIELDS}, 'created_at': now()}
        result = users.insert_one(user)
        database.alumni.insert_one({'user_id': str(result.inserted_id), 'name': user['name'], 'role': requested_role['code'], 'updated_at': now()})
        return Response({'id': str(result.inserted_id), 'name': user['name'], 'email': user['email'], 'role_id': str(requested_role['_id']), 'role': requested_role['code']}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        database = get_database()
        user = database.users.find_one({'email': data['email'].lower()})
        if user and user.get('role_id'):
            role = database.roles.find_one({'_id': user['role_id']})
            if role:
                user['role'] = role['code']
        if not user or not check_password(data['password'], user.get('password', '')):
            return Response({'detail': 'Invalid email or password.'}, status=status.HTTP_401_UNAUTHORIZED)
        if user.get('is_active', True) is False:
            return Response({'detail': 'This account has been disabled.'}, status=status.HTTP_403_FORBIDDEN)
        response = Response({'user': {'id': str(user['_id']), 'name': user['name'], 'email': user['email'], 'role': user['role']}})
        set_auth_cookies(response, user['_id'])
        return response


class ForgotPasswordView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email'].lower()
        user = get_database().users.find_one({'email': email})
        if user:
            otp = make_otp()
            get_database().password_otps.insert_one({'email': email, 'otp_hash': make_password(otp), 'created_at': now(), 'expires_at': now() + timedelta(seconds=settings.OTP_EXPIRY_SECONDS), 'used': False, 'attempts': 0})
            send_mail('Alumni Meet password reset OTP', f'Your password reset OTP is {otp}. It expires in {settings.OTP_EXPIRY_SECONDS // 60} minutes.', settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
        return Response({'detail': 'If an account exists for that email, a reset OTP has been sent.'})


class ResetPasswordView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        database = get_database()
        otp_record = database.password_otps.find_one({'email': data['email'].lower(), 'used': False}, sort=[('created_at', -1)])
        if not otp_record or otp_expired(otp_record['expires_at']) or otp_record.get('attempts', 0) >= settings.OTP_MAX_ATTEMPTS:
            return Response({'detail': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
        if not check_password(data['otp'], otp_record['otp_hash']):
            database.password_otps.update_one({'_id': otp_record['_id']}, {'$inc': {'attempts': 1}})
            return Response({'detail': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
        result = database.users.update_one({'email': data['email'].lower()}, {'$set': {'password': make_password(data['new_password']), 'updated_at': now()}})
        if not result.matched_count:
            return Response({'detail': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
        database.password_otps.update_one({'_id': otp_record['_id']}, {'$set': {'used': True, 'used_at': now()}})
        return Response({'detail': 'Password reset successfully.'})


class ChangePasswordView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserActionRateThrottle]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if data['current_password'] == data['new_password']:
            return Response({'detail': 'New password must be different from the current password.'}, status=status.HTTP_400_BAD_REQUEST)
        database = get_database()
        user = database.users.find_one({'_id': ObjectId(request.user['id'])})
        if not user or not check_password(data['current_password'], user.get('password', '')):
            return Response({'detail': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)
        database.users.update_one({'_id': user['_id']}, {'$set': {'password': make_password(data['new_password']), 'updated_at': now()}})
        return Response({'detail': 'Password changed successfully.'})


class RefreshView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            payload = decode_token(request.COOKIES['refresh_token'], 'refresh')
        except (KeyError, ValueError) as error:
            return Response({'detail': str(error)}, status=status.HTTP_401_UNAUTHORIZED)
        response = Response({'status': 'refreshed'})
        response.set_cookie('access_token', create_token(payload['sub'], 'access', settings.JWT_ACCESS_MINUTES), httponly=True, secure=not settings.DEBUG, samesite='Lax', max_age=settings.JWT_ACCESS_MINUTES * 60)
        return response


class LogoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        response = Response({'status': 'signed out'})
        response.delete_cookie('access_token')
        response.delete_cookie('refresh_token')
        return response


class ProfileView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_database().alumni.find_one({'user_id': request.user['id']}) or {}
        profile_data = serialize(profile) or {}
        profile_data.pop('id', None)
        profile_data.pop('role', None)
        return Response({**profile_data, 'id': request.user['id'], 'name': request.user.get('name'), 'email': request.user.get('email'), 'role': request.user.get('role')})

    def put(self, request):
        serializer = ProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        database = get_database()
        if 'name' in data:
            updated_name = data.pop('name')
            database.users.update_one({'_id': ObjectId(request.user['id'])}, {'$set': {'name': updated_name}})
            data['name'] = updated_name
        database.alumni.update_one({'user_id': request.user['id']}, {'$set': {**data, 'user_id': request.user['id'], 'updated_at': now()}}, upsert=True)
        database.users.update_one({'_id': ObjectId(request.user['id'])}, {'$set': {field: data[field] for field in PROFILE_FIELDS if field in data}})
        updated_user = database.users.find_one({'_id': ObjectId(request.user['id'])}, {'name': 1, 'email': 1}) or request.user
        saved_profile = serialize(database.alumni.find_one({'user_id': request.user['id']}) or {}) or {}
        saved_profile.pop('id', None)
        saved_profile.pop('role', None)
        return Response({**saved_profile, 'id': request.user['id'], 'name': updated_user.get('name'), 'email': updated_user.get('email'), 'role': request.user.get('role')})


class ProfileImagesView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        urls = getattr(request, 'uploaded_profile_urls', None)
        if not urls:
            return Response({'detail': 'Profile image upload could not be processed.'}, status=status.HTTP_400_BAD_REQUEST)
        database = get_database()
        database.alumni.update_one({'user_id': request.user['id']}, {'$set': {**urls, 'user_id': request.user['id'], 'updated_at': now()}}, upsert=True)
        database.users.update_one({'_id': ObjectId(request.user['id'])}, {'$set': urls})
        return Response(urls, status=status.HTTP_201_CREATED)


class AlumniListView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        results = get_alumni()
        page = max(int(request.query_params.get('page', 1)), 1)
        page_size = min(max(int(request.query_params.get('page_size', 24)), 1), 100)
        start = (page - 1) * page_size
        return Response({'results': results[start:start + page_size], 'count': len(results), 'page': page, 'page_size': page_size, 'has_next': start + page_size < len(results)})


class AdminPeopleView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        return Response({'results': get_alumni()})

    def post(self, request):
        serializer = AdminPersonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        email = data.pop('email', '').lower()
        user = get_database().users.find_one({'email': email})
        if not user:
            return Response({'detail': 'Create the member account before adding a profile.'}, status=status.HTTP_400_BAD_REQUEST)
        database = get_database()
        role = get_role(database, data.pop('role', 'alumni'))
        if not role or role['code'] == 'super_admin':
            return Response({'detail': 'People can only be assigned alumni or student roles here.'}, status=status.HTTP_400_BAD_REQUEST)
        database.users.update_one({'_id': user['_id']}, {'$set': {'role_id': role['_id'], 'role': role['code']}})
        profile = {**data, 'role': role['code'], 'user_id': str(user['_id']), 'updated_at': now()}
        database.alumni.update_one({'user_id': str(user['_id'])}, {'$set': profile}, upsert=True)
        return Response(serialize(profile), status=status.HTTP_201_CREATED)


class AdminPersonDetailView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdmin]

    def put(self, request, person_id):
        serializer = AdminPersonSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        database = get_database()
        data.pop('email', None)
        role_code = data.pop('role', None)
        is_active = data.pop('is_active', None)
        profile_update = {**data, 'updated_at': now()}
        if role_code:
            role = get_role(database, role_code)
            if not role or role['code'] == 'super_admin':
                return Response({'detail': 'People can only be assigned alumni or student roles here.'}, status=status.HTTP_400_BAD_REQUEST)
            database.users.update_one({'_id': ObjectId(person_id)}, {'$set': {'role_id': role['_id'], 'role': role['code']}})
            profile_update['role'] = role['code']
        if is_active is not None:
            database.users.update_one({'_id': ObjectId(person_id)}, {'$set': {'is_active': is_active}})
        database.alumni.update_one({'user_id': person_id}, {'$set': profile_update}, upsert=True)
        return Response({'id': person_id, **data})

    def delete(self, request, person_id):
        get_database().alumni.delete_one({'user_id': person_id})
        return Response(status=status.HTTP_204_NO_CONTENT)


class EventListView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsAdmin()]
        return [IsAuthenticated()]

    def get(self, request):
        filters = {key: request.query_params.get(key) for key in ('event_type', 'location', 'status', 'date_from', 'date_to')}
        for key in ('date_from', 'date_to'):
            if filters[key]:
                try:
                    filters[key] = datetime.fromisoformat(filters[key]).replace(tzinfo=timezone.utc)
                except ValueError:
                    return Response({'detail': f'Invalid {key} value.'}, status=status.HTTP_400_BAD_REQUEST)
        results = get_events(filters)
        page = max(int(request.query_params.get('page', 1)), 1)
        page_size = min(max(int(request.query_params.get('page_size', 12)), 1), 50)
        start = (page - 1) * page_size
        return Response({'results': results[start:start + page_size], 'count': len(results), 'page': page, 'page_size': page_size, 'has_next': start + page_size < len(results)})

    def post(self, request):
        serializer = EventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        event_date = datetime.combine(data.pop('date'), data.pop('time'), tzinfo=timezone.utc)
        event = {**mongo_safe(data), 'date': event_date, 'time': event_date.time().replace(microsecond=0).isoformat(), 'created_by': request.user['id'], 'created_at': now(), 'updated_at': now()}
        result = get_database().events.insert_one(event)
        return Response(serialize({**event, '_id': result.inserted_id}), status=status.HTTP_201_CREATED)


class EventDetailView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        event = get_event(event_id)
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)
        event['is_registered'] = any(item['id'] == request.user['id'] for item in event['participants'])
        registration = get_database().event_registrations.find_one({'event_id': event_id, 'user_id': request.user['id']})
        if registration:
            event['registration_status'] = registration.get('status')
            event['qr_code'] = registration.get('qr_code')
        return Response(event)


class AdminEventDetailView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdmin]

    def put(self, request, event_id):
        serializer = AdminEventSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if 'date' in data and 'time' in data:
            date_value = data.pop('date')
            time_value = data.pop('time')
            combined = datetime.combine(date_value, time_value, tzinfo=timezone.utc)
            data.update({'date': combined, 'time': combined.time().replace(microsecond=0).isoformat()})
        try:
            object_id = ObjectId(event_id)
        except Exception:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)
        result = get_database().events.update_one({'_id': object_id}, {'$set': {**mongo_safe(data), 'updated_at': now()}})
        if not result.matched_count:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize(get_database().events.find_one({'_id': object_id})))

    def delete(self, request, event_id):
        try:
            result = get_database().events.delete_one({'_id': ObjectId(event_id)})
        except Exception:
            result = None
        if not result or not result.deleted_count:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RSVPView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserActionRateThrottle]

    def post(self, request, event_id):
        serializer = RSVPSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        database = get_database()
        try:
            event = database.events.find_one({'_id': ObjectId(event_id)})
        except Exception:
            event = None
        if not event:
            return Response({'detail': 'Event not found.'}, status=status.HTTP_404_NOT_FOUND)
        existing = database.event_registrations.find_one({'event_id': event_id, 'user_id': request.user['id']})
        if not existing and database.event_registrations.count_documents({'event_id': event_id, 'status': 'registered'}) >= event.get('capacity', 100):
            return Response({'detail': 'This event is at capacity.'}, status=status.HTTP_409_CONFLICT)
        registration = existing or {}
        token = registration.get('qr_token') or secrets.token_urlsafe(32)
        verification_url = registration_url(token)
        qr_code = registration_qr(token)
        registration_status = serializer.validated_data['status']
        database.event_registrations.update_one({'event_id': event_id, 'user_id': request.user['id']}, {'$set': {'status': registration_status, 'qr_token': token, 'qr_url': verification_url, 'qr_code': qr_code, 'user': request.user['id'], 'event': event_id, 'updated_at': now()}, '$setOnInsert': {'created_at': now()}}, upsert=True)
        if registration_status == 'registered':
            send_mail('RSVP confirmed: ' + event.get('title', 'Alumni event'), f'Your registration for {event.get("title", "the event")} is confirmed.\n\nEntry URL: {verification_url}', settings.DEFAULT_FROM_EMAIL, [request.user['email']], fail_silently=True)
        return Response({'event_id': event_id, 'status': serializer.validated_data['status'], 'qr_token': token, 'qr_url': verification_url, 'qr_code': qr_code}, status=status.HTTP_201_CREATED)


class EventCheckInView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdmin]
    throttle_classes = [UserActionRateThrottle]

    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        database = get_database()
        token = registration_token(serializer.validated_data['token'])
        registration = database.event_registrations.find_one({'qr_token': token})
        if not registration:
            return Response({'detail': 'QR code is not valid.'}, status=status.HTTP_404_NOT_FOUND)
        if registration.get('status') == 'attended':
            return Response({'detail': 'This registration has already been checked in.'}, status=status.HTTP_409_CONFLICT)
        try:
            user = database.users.find_one({'_id': ObjectId(registration['user_id'])}, {'name': 1, 'email': 1})
            event = database.events.find_one({'_id': ObjectId(registration['event_id'])}, {'title': 1})
        except Exception:
            user = None
            event = None
        if not user or not event:
            return Response({'detail': 'The QR registration is missing its user or event details.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        checked_in_at = now()
        result = database.event_registrations.update_one({'_id': registration['_id'], 'status': 'registered'}, {'$set': {'status': 'attended', 'checked_in_at': checked_in_at, 'updated_at': checked_in_at}})
        if not result.modified_count:
            return Response({'detail': 'This registration has already been checked in.'}, status=status.HTTP_409_CONFLICT)
        database.attendance.update_one({'registration_id': registration['_id']}, {'$set': {'registration_id': registration['_id'], 'event_id': registration['event_id'], 'user_id': registration['user_id'], 'checked_in_at': checked_in_at}}, upsert=True)
        return Response({'event_id': registration['event_id'], 'event_title': event.get('title') if event else None, 'attendee': serialize(user), 'status': 'attended'})


class AlumniDetailView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, person_id):
        try:
            profile = get_database().alumni.find_one({'$or': [{'_id': ObjectId(person_id)}, {'user_id': person_id}]})
        except Exception:
            profile = get_database().alumni.find_one({'user_id': person_id})
        if not profile or profile.get('role') == 'super_admin':
            return Response({'detail': 'Profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        user = get_database().users.find_one({'_id': ObjectId(profile['user_id'])}, {'name': 1, 'email': 1})
        return Response({**(serialize(profile) or {}), **(serialize(user) or {})})


class AttendanceView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        database = get_database()
        rows = []
        for attendance in database.attendance.find().sort('checked_in_at', -1):
            user = database.users.find_one({'_id': ObjectId(attendance['user_id'])}, {'name': 1, 'email': 1})
            event = database.events.find_one({'_id': ObjectId(attendance['event_id'])}, {'title': 1})
            if user and event:
                rows.append({'id': str(attendance['_id']), 'attendee': user.get('name'), 'email': user.get('email'), 'event_id': attendance['event_id'], 'event_title': event.get('title'), 'checked_in_at': attendance.get('checked_in_at')})
        if request.query_params.get('download') == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="attendance.csv"'
            writer = csv.writer(response)
            writer.writerow(('attendee', 'email', 'event_title', 'checked_in_at'))
            for row in rows:
                writer.writerow(tuple(row.get(key) or '' for key in ('attendee', 'email', 'event_title', 'checked_in_at')))
            return response
        return Response({'results': rows, 'count': len(rows)})


class AnalyticsView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        database = get_database()
        users = list(database.users.find({}, {'created_at': 1, 'role': 1, 'is_active': 1}))
        events = list(database.events.find({}, {'date': 1, 'status': 1, 'capacity': 1}))
        registrations = list(database.event_registrations.find({}, {'status': 1, 'event_id': 1}))
        growth = 0
        for user in users:
            created_at = user.get('created_at')
            if created_at:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                growth += (now() - created_at).total_seconds() <= 30 * 86400
        return Response({'users': {'total': len(users), 'active': sum(user.get('is_active', True) is not False for user in users), 'disabled': sum(user.get('is_active', True) is False for user in users)}, 'events': {'total': len(events), 'upcoming': sum(event.get('status', 'upcoming') == 'upcoming' for event in events), 'cancelled': sum(event.get('status') == 'cancelled' for event in events)}, 'participation': {'registrations': sum(item.get('status') == 'registered' for item in registrations), 'attended': sum(item.get('status') == 'attended' for item in registrations), 'cancelled': sum(item.get('status') == 'cancelled' for item in registrations)}, 'growth': {'users_last_30_days': growth}})


class MyEventsView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        database = get_database()
        results = []
        for registration in database.event_registrations.find({'user_id': request.user['id']}).sort('updated_at', -1):
            item = serialize(registration)
            try:
                event = database.events.find_one({'_id': ObjectId(registration['event_id'])})
            except Exception:
                event = None
            if event:
                item['event'] = normalize_event(event)
                item['event_title'] = event.get('title')
            results.append(item)
        return Response({'results': results})
