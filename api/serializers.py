from decimal import Decimal

from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, max_length=128, write_only=True)
    role_id = serializers.CharField(required=False, allow_blank=True)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.RegexField(regex=r'^\d{6}$')
    new_password = serializers.CharField(min_length=8, max_length=128, write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(min_length=8, max_length=128, write_only=True)


class ProfileSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=100, required=False)
    batch_year = serializers.IntegerField(min_value=1900, max_value=2100, required=False)
    current_company = serializers.CharField(max_length=150, required=False, allow_blank=True)
    job_title = serializers.CharField(max_length=150, required=False, allow_blank=True)
    location = serializers.CharField(max_length=100, required=False, allow_blank=True)
    bio = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    phone_country_code = serializers.RegexField(regex=r'^\+[1-9]\d{0,3}$', required=False)
    phone_number = serializers.RegexField(regex=r'^\d{6,15}$', required=False, allow_blank=True)
    address = serializers.CharField(max_length=300, required=False, allow_blank=True)
    country = serializers.CharField(max_length=100, required=False, allow_blank=True)
    pincode = serializers.RegexField(regex=r'^\d{4,10}$', required=False, allow_blank=True)


class EventSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=3, max_length=150)
    description = serializers.CharField(max_length=2000)
    date = serializers.DateField()
    time = serializers.TimeField()
    location = serializers.CharField(min_length=2, max_length=200)
    created_by = serializers.CharField(required=False, read_only=True)
    event_type = serializers.ChoiceField(choices=['offline', 'online', 'hybrid'], default='offline')
    banner_image = serializers.URLField(required=False, allow_blank=True)
    capacity = serializers.IntegerField(min_value=1, max_value=100000, required=False, default=100)
    registration_deadline = serializers.DateTimeField(required=False, allow_null=True)
    is_free = serializers.BooleanField(default=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0'), required=False, default=Decimal('0'))
    status = serializers.ChoiceField(choices=['upcoming', 'completed', 'cancelled'], default='upcoming')
    waitlist_enabled = serializers.BooleanField(default=False)
    is_active = serializers.BooleanField(default=True)


class RSVPSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['registered', 'cancelled'], default='registered')


class CheckInSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=20, max_length=500)


class AdminPersonSerializer(ProfileSerializer):
    email = serializers.EmailField(required=False)
    role = serializers.ChoiceField(choices=['alumni', 'student'], default='alumni')
    is_active = serializers.BooleanField(required=False)


class AdminEventSerializer(EventSerializer):
    pass
