from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'


class RegisterRateThrottle(AnonRateThrottle):
    scope = 'register'


class UserActionRateThrottle(UserRateThrottle):
    scope = 'user_actions'


class PasswordResetRateThrottle(AnonRateThrottle):
    scope = 'password_reset'
