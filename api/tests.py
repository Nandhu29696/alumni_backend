from datetime import datetime, timezone
from unittest.mock import patch

import mongomock
from bson import ObjectId
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient


class AlumniApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.mongo = mongomock.MongoClient()
        self.database = self.mongo.alumni_meet
        self.database.roles.insert_many([
            {'code': 'alumni', 'name': 'Alumni'},
            {'code': 'student', 'name': 'Student'},
            {'code': 'super_admin', 'name': 'Super administrator'},
        ])
        self.database.users.create_index('email', unique=True)
        self.database.event_registrations.create_index([('event_id', 1), ('user_id', 1)], unique=True)
        self.database.attendance.create_index([('registration_id', 1)], unique=True)
        self.database.events.insert_one({'_id': ObjectId(), 'title': 'Homecoming', 'description': 'Reconnect', 'date': datetime(2026, 10, 18, tzinfo=timezone.utc), 'location': 'Auditorium', 'capacity': 1})
        self.database.events.find_one()
        self.patches = [patch('api.views.get_database', return_value=self.database), patch('api.repository.get_database', return_value=self.database)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()

    def test_register_login_and_protected_profile(self):
        response = self.client.post('/api/auth/register/', {'name': 'Samir Kapoor', 'email': 'samir@example.com', 'password': 'secure-pass-123'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertNotEqual(self.database.users.find_one()['password'], 'secure-pass-123')
        response = self.client.post('/api/auth/login/', {'email': 'samir@example.com', 'password': 'secure-pass-123'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('access_token', response.cookies)
        response = self.client.get('/api/auth/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Samir Kapoor')

    def test_super_admin_profile_keeps_authoritative_role(self):
        from api.tokens import create_token

        admin_role = self.database.roles.find_one({'code': 'super_admin'})
        admin_id = self.database.users.insert_one({'name': 'Admin', 'email': 'admin@example.com', 'password': 'unused', 'role_id': admin_role['_id'], 'role': 'super_admin'}).inserted_id
        self.database.alumni.insert_one({'user_id': str(admin_id), 'name': 'Admin', 'role': 'alumni'})
        self.client.cookies['access_token'] = create_token(admin_id, 'access', 60)
        response = self.client.get('/api/auth/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['role'], 'super_admin')

    def test_profile_update_returns_json_safe_profile(self):
        self.client.post('/api/auth/register/', {'name': 'Samir Kapoor', 'email': 'samir@example.com', 'password': 'secure-pass-123'}, format='json')
        self.client.post('/api/auth/login/', {'email': 'samir@example.com', 'password': 'secure-pass-123'}, format='json')
        response = self.client.put('/api/auth/profile/', {'name': 'Samir Updated', 'batch_year': 2012, 'bio': 'Updated bio', 'phone_country_code': '+91', 'phone_number': '9876543210', 'address': '12 Main Street', 'country': 'India', 'pincode': '560001'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Samir Updated')
        self.assertEqual(response.data['batch_year'], 2012)
        self.assertEqual(response.data['bio'], 'Updated bio')
        self.assertEqual(response.data['phone_country_code'], '+91')
        self.assertEqual(response.data['phone_number'], '9876543210')
        user = self.database.users.find_one({'email': 'samir@example.com'})
        self.assertEqual(user['batch_year'], 2012)
        self.assertEqual(user['bio'], 'Updated bio')
        self.assertEqual(user['country'], 'India')
        self.assertEqual(user['pincode'], '560001')

    @patch('api.views.send_mail')
    def test_password_otp_reset_is_one_time(self, send_mail):
        self.client.post('/api/auth/register/', {'name': 'Samir Kapoor', 'email': 'samir@example.com', 'password': 'secure-pass-123'}, format='json')
        response = self.client.post('/api/auth/password/forgot/', {'email': 'samir@example.com'}, format='json')
        self.assertEqual(response.status_code, 200)
        otp_record = self.database.password_otps.find_one()
        otp = send_mail.call_args.args[1].split(' is ')[1].split('.')[0]
        reset = self.client.post('/api/auth/password/reset/', {'email': 'samir@example.com', 'otp': otp, 'new_password': 'new-secure-pass-123'}, format='json')
        self.assertEqual(reset.status_code, 200)
        self.assertTrue(self.database.password_otps.find_one({'_id': otp_record['_id']})['used'])
        repeat = self.client.post('/api/auth/password/reset/', {'email': 'samir@example.com', 'otp': otp, 'new_password': 'another-secure-pass-123'}, format='json')
        self.assertEqual(repeat.status_code, 400)

    def test_authenticated_password_change(self):
        self.client.post('/api/auth/register/', {'name': 'Samir Kapoor', 'email': 'samir@example.com', 'password': 'secure-pass-123'}, format='json')
        self.client.post('/api/auth/login/', {'email': 'samir@example.com', 'password': 'secure-pass-123'}, format='json')
        response = self.client.post('/api/auth/password/change/', {'current_password': 'secure-pass-123', 'new_password': 'new-secure-pass-123'}, format='json')
        self.assertEqual(response.status_code, 200)

    def test_public_registration_ignores_stale_auth_cookie(self):
        self.client.cookies['access_token'] = 'token-for-deleted-user'
        response = self.client.post('/api/auth/register/', {'name': 'New Member', 'email': 'new@example.com', 'password': 'secure-pass-123'}, format='json')
        self.assertEqual(response.status_code, 201)

    def test_protected_endpoint_rejects_anonymous_user(self):
        response = self.client.get('/api/alumni/')
        self.assertEqual(response.status_code, 401)

    def test_rsvp_is_persistent_and_duplicate_safe(self):
        self.client.post('/api/auth/register/', {'name': 'Aarav Menon', 'email': 'aarav@example.com', 'password': 'secure-pass-123'}, format='json')
        self.client.post('/api/auth/login/', {'email': 'aarav@example.com', 'password': 'secure-pass-123'}, format='json')
        event_id = str(self.database.events.find_one()['_id'])
        first = self.client.post(f'/api/events/{event_id}/register/', {}, format='json')
        second = self.client.post(f'/api/events/{event_id}/register/', {}, format='json')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(self.database.event_registrations.count_documents({'event_id': event_id}), 1)

    def test_registration_qr_can_check_in_once(self):
        from api.tokens import create_token

        self.client.post('/api/auth/register/', {'name': 'Aarav Menon', 'email': 'aarav@example.com', 'password': 'secure-pass-123'}, format='json')
        self.client.post('/api/auth/login/', {'email': 'aarav@example.com', 'password': 'secure-pass-123'}, format='json')
        event_id = str(self.database.events.find_one()['_id'])
        registration = self.client.post(f'/api/events/{event_id}/register/', {}, format='json')
        token = registration.data['qr_token']
        qr_url = registration.data['qr_url']
        self.assertTrue(registration.data['qr_code'].startswith('data:image/png;base64,'))
        self.assertTrue(registration.data['qr_url'].startswith('http://localhost:3000/check-in?token='))
        admin_role = self.database.roles.find_one({'code': 'super_admin'})
        admin_id = self.database.users.insert_one({'name': 'Admin', 'email': 'admin@example.com', 'password': 'unused', 'role_id': admin_role['_id'], 'role': 'super_admin'}).inserted_id
        self.client.cookies['access_token'] = create_token(admin_id, 'access', 60)
        self.assertEqual(self.client.post('/api/admin/events/check-in/', {'token': 'invalid-token'}, format='json').status_code, 400)
        checked_in = self.client.post('/api/admin/events/check-in/', {'token': qr_url}, format='json')
        self.assertEqual(checked_in.status_code, 200)
        self.assertEqual(checked_in.data['status'], 'attended')
        self.assertEqual(checked_in.data['attendee']['name'], 'Aarav Menon')
        self.assertEqual(checked_in.data['attendee']['email'], 'aarav@example.com')
        self.assertEqual(checked_in.data['event_title'], 'Homecoming')
        self.assertEqual(self.database.event_registrations.find_one({'event_id': event_id})['status'], 'attended')
        self.assertEqual(self.database.attendance.count_documents({'event_id': event_id}), 1)
        self.assertEqual(self.client.post('/api/admin/events/check-in/', {'token': token}, format='json').status_code, 409)

    def test_attendance_csv_export(self):
        from api.tokens import create_token

        admin_role = self.database.roles.find_one({'code': 'super_admin'})
        admin_id = self.database.users.insert_one({'name': 'Admin', 'email': 'admin@example.com', 'password': 'unused', 'role_id': admin_role['_id'], 'role': 'super_admin'}).inserted_id
        self.client.cookies['access_token'] = create_token(admin_id, 'access', 60)
        response = self.client.get('/api/admin/attendance/?download=csv')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])

    def test_admin_event_update_encodes_paid_price_for_mongodb(self):
        from api.tokens import create_token

        admin_role = self.database.roles.find_one({'code': 'super_admin'})
        admin_id = self.database.users.insert_one({'name': 'Admin', 'email': 'admin@example.com', 'password': 'unused', 'role_id': admin_role['_id'], 'role': 'super_admin'}).inserted_id
        self.client.cookies['access_token'] = create_token(admin_id, 'access', 60)
        event_id = str(self.database.events.find_one()['_id'])
        response = self.client.put(f'/api/admin/events/{event_id}/', {'title': 'Updated', 'description': 'Updated details', 'date': '2026-10-18', 'time': '18:30', 'location': 'Hall', 'event_type': 'offline', 'price': '100.00'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.database.events.find_one({'_id': ObjectId(event_id)})['price'], 100.0)
