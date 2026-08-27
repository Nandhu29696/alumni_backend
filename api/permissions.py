from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    message = 'Administrator access is required.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.get('role') in {'admin', 'super_admin'})
