from django.core.management.base import BaseCommand

from api.repository import get_database, normalize_event, now


class Command(BaseCommand):
    help = 'Backfill the Phase 1 event fields on existing MongoDB event documents.'

    def handle(self, *args, **options):
        database = get_database()
        updated = 0
        for event in database.events.find():
            normalized = normalize_event(event)
            fields = {
                'date': event.get('date'),
                'time': normalized.get('time'),
                'event_type': normalized.get('event_type'),
                'banner_image': normalized.get('banner_image'),
                'capacity': normalized.get('capacity'),
                'registration_deadline': normalized.get('registration_deadline'),
                'is_free': normalized.get('is_free'),
                'price': float(normalized.get('price', 0)),
                'status': normalized.get('status'),
                'waitlist_enabled': normalized.get('waitlist_enabled'),
                'is_active': normalized.get('is_active'),
                'updated_at': now(),
            }
            if fields['date'] is None:
                fields.pop('date')
            database.events.update_one({'_id': event['_id']}, {'$set': fields, '$setOnInsert': {'created_at': now()}})
            updated += 1
        self.stdout.write(self.style.SUCCESS(f'Backfilled {updated} event documents.'))
