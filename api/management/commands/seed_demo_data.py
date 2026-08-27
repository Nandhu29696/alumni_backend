from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from api.repository import get_database, get_role, now


FIRST_NAMES = ['Aarav', 'Ananya', 'Arjun', 'Diya', 'Esha', 'Ishaan', 'Kabir', 'Kavya', 'Meera', 'Nisha', 'Rohan', 'Sana', 'Vihaan', 'Zoya']
LAST_NAMES = ['Menon', 'Iyer', 'Shah', 'Krishnan', 'Kapoor', 'Patel', 'Reddy', 'Bose', 'Nair', 'Joshi', 'Malhotra', 'Chopra']
JOBS = [('Product Designer', 'Lattice'), ('Software Engineer', 'Razorpay'), ('Founder', 'Terra'), ('Climate Researcher', 'IISc'), ('Marketing Lead', 'Myntra'), ('Architect', 'Studio North'), ('Doctor', 'Apollo Hospitals'), ('Data Scientist', 'Microsoft')]
LOCATIONS = ['Bengaluru', 'Mumbai', 'Pune', 'Chennai', 'Delhi', 'Hyderabad', 'Kochi', 'Kolkata']
EVENTS = [
    ('The annual homecoming', 'Reconnect with classmates over an evening at school.', 'School auditorium'),
    ('Founders and future-makers', 'A conversation with alumni building the next generation of companies.', 'The Common Room'),
    ('Mentorship circle', 'An open session for students and alumni to share practical advice.', 'Online gathering'),
    ('Bengaluru chapter dinner', 'An informal dinner for alumni living in and around Bengaluru.', 'The Courtyard'),
    ('Mumbai rooftop social', 'Meet old friends and make new connections over sunset drinks.', 'Harbour House'),
    ('Creative alumni showcase', 'See what our community is making across art, design, and media.', 'Arts Block'),
    ('Career switch stories', 'Honest stories from alumni who changed industries and started again.', 'Lecture Hall 2'),
    ('Sports day return', 'Bring back the friendly competition with alumni teams.', 'School grounds'),
    ('Women in leadership', 'A focused roundtable on leadership, confidence, and opportunity.', 'The Library'),
    ('Community service morning', 'Give back together through a local volunteering morning.', 'Main gate'),
    ('Young alumni breakfast', 'A relaxed breakfast for recent graduates and early-career alumni.', 'Cedar Cafe'),
    ('Year-end celebration', 'Close the year with the whole community under one roof.', 'School courtyard'),
]


class Command(BaseCommand):
    help = 'Create repeatable sample roles, users, alumni profiles, and events in MongoDB.'

    def add_arguments(self, parser):
        parser.add_argument('--people', type=int, default=60)
        parser.add_argument('--events', type=int, default=12)
        parser.add_argument('--password', default='AlumniDemo123!')
        parser.add_argument('--admin-email', default='superadmin@alumnimeet.local')
        parser.add_argument('--admin-name', default='Alumni Meet Super Admin')

    def handle(self, *args, **options):
        database = get_database()
        alumni_role = get_role(database, 'alumni')
        admin_role = get_role(database, 'super_admin')
        password = make_password(options['password'])

        admin = database.users.find_one({'email': options['admin_email'].lower()})
        if not admin:
            database.users.insert_one({'name': options['admin_name'], 'email': options['admin_email'].lower(), 'password': password, 'role_id': admin_role['_id'], 'role': 'super_admin', 'created_at': now()})
        else:
            database.users.update_one({'_id': admin['_id']}, {'$set': {'role_id': admin_role['_id'], 'role': 'super_admin'}})

        people_created = 0
        for index in range(options['people']):
            name = f'{FIRST_NAMES[index % len(FIRST_NAMES)]} {LAST_NAMES[(index * 3) % len(LAST_NAMES)]}'
            email = f'alumni{index + 1:03d}@alumnimeet.local'
            user = database.users.find_one({'email': email})
            if not user:
                result = database.users.insert_one({'name': name, 'email': email, 'password': password, 'role_id': alumni_role['_id'], 'role': 'alumni', 'created_at': now()})
                user_id = str(result.inserted_id)
                people_created += 1
            else:
                user_id = str(user['_id'])
            job, company = JOBS[index % len(JOBS)]
            database.alumni.update_one({'user_id': user_id}, {'$setOnInsert': {'user_id': user_id, 'name': name, 'batch_year': 2005 + (index % 16), 'current_company': company, 'job_title': job, 'location': LOCATIONS[index % len(LOCATIONS)], 'bio': 'Alumni member building meaningful work and staying connected to the community.', 'role': 'alumni', 'updated_at': now()}}, upsert=True)

        events_created = 0
        for index, (title, description, location) in enumerate(EVENTS[:options['events']]):
            if database.events.find_one({'title': title}):
                continue
            database.events.insert_one({'title': title, 'description': description, 'date': now() + timedelta(days=45 + index * 14), 'location': location, 'capacity': 50 + index * 10, 'created_by': str(admin['_id']) if admin else options['admin_email'], 'created_at': now()})
            events_created += 1

        self.stdout.write(self.style.SUCCESS(f'Seed complete: {people_created} new people, {events_created} new events.'))
        self.stdout.write(f'Demo member password: {options["password"]}')
        self.stdout.write(f'Super admin email: {options["admin_email"]}')
