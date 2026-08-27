from bson import ObjectId
from django.core.management.base import BaseCommand

from api.repository import get_database


PROFILE_FIELDS = ('batch_year', 'current_company', 'job_title', 'location', 'bio', 'avatar_image', 'cover_image', 'phone_country_code', 'phone_number', 'address', 'country', 'pincode')


class Command(BaseCommand):
    help = 'Copy alumni profile fields into matching MongoDB user documents.'

    def handle(self, *args, **options):
        database = get_database()
        defaults = {field: None for field in PROFILE_FIELDS}
        database.users.update_many({}, {'$setOnInsert': defaults}, upsert=False)
        for field, value in defaults.items():
            database.users.update_many({field: {'$exists': False}}, {'$set': {field: value}})
        updated = 0
        for profile in database.alumni.find({'user_id': {'$exists': True}}):
            values = {field: profile[field] for field in PROFILE_FIELDS if field in profile}
            if values:
                result = database.users.update_one({'_id': ObjectId(profile['user_id'])}, {'$set': values})
                updated += result.modified_count
        self.stdout.write(self.style.SUCCESS(f'Backfilled {updated} user profile records.'))
