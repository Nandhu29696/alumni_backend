from django.core.management.base import BaseCommand

from api.repository import get_database


class Command(BaseCommand):
    help = 'Copy legacy registrations into event_registrations.'

    def handle(self, *args, **options):
        database = get_database()
        copied = 0
        for registration in database.registrations.find():
            legacy_id = registration.pop('_id', None)
            registration['user'] = registration.get('user_id')
            registration['event'] = registration.get('event_id')
            result = database.event_registrations.update_one(
                {'event_id': registration.get('event_id'), 'user_id': registration.get('user_id')},
                {'$setOnInsert': registration},
                upsert=True,
            )
            if result.upserted_id:
                copied += 1
        for registration in database.event_registrations.find({'status': 'attended', 'checked_in_at': {'$exists': True}}):
            database.attendance.update_one({'registration_id': registration['_id']}, {'$set': {'registration_id': registration['_id'], 'event_id': registration['event_id'], 'user_id': registration['user_id'], 'checked_in_at': registration['checked_in_at']}}, upsert=True)
        self.stdout.write(self.style.SUCCESS(f'Migrated {copied} registrations to event_registrations.'))
