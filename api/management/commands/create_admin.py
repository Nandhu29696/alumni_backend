from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from api.repository import get_database, now


class Command(BaseCommand):
    help = 'Create or promote a MongoDB user as an Alumni Meet administrator.'

    def add_arguments(self, parser):
        parser.add_argument('email')
        parser.add_argument('name')
        parser.add_argument('--password', required=True)

    def handle(self, *args, **options):
        if len(options['password']) < 8:
            raise CommandError('Password must be at least 8 characters.')
        users = get_database().users
        user = users.find_one({'email': options['email'].lower()})
        role = get_database().roles.find_one({'code': 'super_admin'})
        document = {'name': options['name'], 'email': options['email'].lower(), 'password': make_password(options['password']), 'role_id': role['_id'], 'role': 'super_admin', 'created_at': now()}
        if user:
            users.update_one({'_id': user['_id']}, {'$set': {'name': document['name'], 'password': document['password'], 'role_id': document['role_id'], 'role': 'super_admin'}})
            self.stdout.write(self.style.SUCCESS(f"Promoted {document['email']} to admin."))
        else:
            users.insert_one(document)
            self.stdout.write(self.style.SUCCESS(f"Created admin {document['email']}."))