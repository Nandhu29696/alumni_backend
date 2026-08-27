from datetime import datetime, timezone
from bson import ObjectId
from django.conf import settings
from pymongo import ASCENDING, MongoClient

_client = None
_database = None
_database_initialized = False


def get_database():
    global _client, _database, _database_initialized
    if not settings.MONGODB_URI:
        raise RuntimeError('MONGODB_URI is not configured.')
    if _client is None:
        _client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000, socketTimeoutMS=5000)
    database = _database if _database is not None else _client[settings.MONGODB_NAME]
    if _database_initialized:
        return database
    database.users.create_index([('email', ASCENDING)], unique=True)
    database.roles.create_index([('code', ASCENDING)], unique=True)
    database.event_registrations.create_index([('event_id', ASCENDING), ('user_id', ASCENDING)], unique=True)
    database.event_registrations.create_index([('qr_token', ASCENDING)], unique=True, sparse=True)
    database.event_registrations.create_index([('user_id', ASCENDING), ('status', ASCENDING)])
    database.attendance.create_index([('registration_id', ASCENDING)], unique=True)
    database.attendance.create_index([('event_id', ASCENDING), ('user_id', ASCENDING)])
    database.alumni.create_index([('user_id', ASCENDING)], unique=True, sparse=True)
    database.events.create_index([('date', ASCENDING), ('status', ASCENDING)])
    database.password_otps.create_index([('email', ASCENDING), ('created_at', -1)])
    for code, name in [('alumni', 'Alumni'), ('student', 'Student'), ('super_admin', 'Super administrator')]:
        database.roles.update_one({'code': code}, {'$setOnInsert': {'code': code, 'name': name, 'created_at': now()}}, upsert=True)
    _database = database
    _database_initialized = True
    return database


def serialize(document):
    if not document:
        return None
    result = dict(document)
    result['id'] = str(result.pop('_id')) if '_id' in result else result.get('id')
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
    return result


def now():
    return datetime.now(timezone.utc)


def find_user(user_id):
    try:
        database = get_database()
        user = database.users.find_one({'_id': ObjectId(user_id)})
        if user and user.get('is_active', True) is False:
            return None
        if user and user.get('role_id'):
            role = database.roles.find_one({'_id': user['role_id']})
            if role:
                user['role'] = role['code']
        return user
    except Exception:
        return None


def get_events(filters=None):
    filters = filters or {}
    query = {'is_active': {'$ne': False}}
    for key in ('event_type', 'location', 'status'):
        if filters.get(key):
            query[key] = {'$regex': filters[key], '$options': 'i'} if key == 'location' else filters[key]
    if filters.get('date_from') or filters.get('date_to'):
        query['date'] = {}
        if filters.get('date_from'):
            query['date']['$gte'] = filters['date_from']
        if filters.get('date_to'):
            query['date']['$lte'] = filters['date_to']
    return [normalize_event(item) for item in get_database().events.find(query).sort('date', ASCENDING)]


def normalize_event(document):
    result = serialize(document)
    if not result:
        return result
    value = document.get('date')
    if isinstance(value, datetime):
        result['date'] = value.date().isoformat()
        result.setdefault('time', value.time().replace(microsecond=0).isoformat())
    result.setdefault('event_type', 'offline')
    result.setdefault('banner_image', 'https://images.unsplash.com/photo-1511632765486-a01980e01a18?auto=format&fit=crop&w=1400&q=80')
    result.setdefault('capacity', 100)
    result.setdefault('registration_deadline', None)
    result.setdefault('is_free', True)
    result.setdefault('price', 0)
    result.setdefault('status', 'upcoming')
    result.setdefault('waitlist_enabled', False)
    result.setdefault('is_active', True)
    return result


def get_event(event_id):
    database = get_database()
    try:
        event = database.events.find_one({'_id': ObjectId(event_id)})
    except Exception:
        return None
    if not event:
        return None
    result = normalize_event(event)
    registrations = list(database.event_registrations.find({'event_id': event_id, 'status': {'$in': ['registered', 'attended']}}))
    result['participants'] = []
    for registration in registrations:
        user = database.users.find_one({'_id': ObjectId(registration['user_id'])}, {'name': 1, 'email': 1})
        if user:
            participant = serialize(user)
            participant['status'] = registration['status']
            result['participants'].append(participant)
    result['participant_count'] = len(result['participants'])
    result['attendees_count'] = result['participant_count']
    result['remaining_capacity'] = max(0, result.get('capacity', 100) - result['participant_count'])
    return result


def get_alumni():
    database = get_database()
    excluded_users = [item['_id'] for item in database.users.find({'role': 'super_admin'}, {'_id': 1})]
    results = []
    for item in database.alumni.find({'role': {'$ne': 'super_admin'}, 'user_id': {'$nin': [str(item) for item in excluded_users]}}).sort('name', ASCENDING):
        result = serialize(item)
        user = database.users.find_one({'_id': ObjectId(item['user_id'])}, {'email': 1, 'role': 1, 'is_active': 1, 'avatar_image': 1, 'cover_image': 1})
        if user:
            result.update({key: user[key] for key in ('email', 'role', 'is_active', 'avatar_image', 'cover_image') if key in user})
        results.append(result)
    return results


def get_role(database, code='alumni'):
    return database.roles.find_one({'code': code})


def get_role_by_id(database, role_id):
    try:
        return database.roles.find_one({'_id': ObjectId(str(role_id))})
    except Exception:
        return None
