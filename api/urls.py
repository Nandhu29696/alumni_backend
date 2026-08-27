from django.urls import path
from . import views
from .views import AdminEventDetailView, AdminPeopleView, AdminPersonDetailView, AlumniDetailView, AlumniListView, AnalyticsView, AttendanceView, ChangePasswordView, CSRFView, EventBannerUploadView, EventCheckInView, EventDetailView, EventListView, ForgotPasswordView, HealthView, LoginView, LogoutView, MyEventsView, ProfileImagesView, ProfileView, RefreshView, RegisterView, ResetPasswordView, RSVPView

urlpatterns = [
    path('health/', HealthView.as_view()),
    path('auth/csrf/', CSRFView.as_view()),
    path('admin/events/upload-banner/', EventBannerUploadView.as_view()),
    path('auth/register/', RegisterView.as_view()),
    path('auth/login/', LoginView.as_view()),
    path('auth/password/forgot/', ForgotPasswordView.as_view()),
    path('auth/password/reset/', ResetPasswordView.as_view()),
    path('auth/password/change/', ChangePasswordView.as_view()),
    path('auth/logout/', LogoutView.as_view()),
    path('auth/refresh/', RefreshView.as_view()),
    path('auth/profile/', ProfileView.as_view()),
    path('auth/profile/images/', ProfileImagesView.as_view()),
    path('alumni/', AlumniListView.as_view()),
    path('alumni/<str:person_id>/', AlumniDetailView.as_view()),
    path('admin/people/', AdminPeopleView.as_view()),
    path('admin/people/<str:person_id>/', AdminPersonDetailView.as_view()),
    path('events/', EventListView.as_view()),
    path('events/<str:event_id>/', EventDetailView.as_view()),
    path('admin/events/check-in/', EventCheckInView.as_view()),
    path('admin/attendance/', AttendanceView.as_view()),
    path('admin/analytics/', AnalyticsView.as_view()),
    path('admin/events/<str:event_id>/', AdminEventDetailView.as_view()),
    path('events/<str:event_id>/register/', RSVPView.as_view()),
    path('my-events/', MyEventsView.as_view()),
]
