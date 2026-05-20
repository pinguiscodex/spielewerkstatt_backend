from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    DataFolderFileDownloadView,
    DataFolderFileView,
    DataFolderView,
    DeveloperAdminViewSet,
    EventViewSet,
    GameFileDownloadView,
    GameViewSet,
    LoginView,
    MeView,
    NewsletterView,
    RegisterDeveloperView,
    ShareFolderView,
    VotingView,
)

router = DefaultRouter()
router.register("games", GameViewSet, basename="games")
router.register("admin/developers", DeveloperAdminViewSet, basename="admin-developers")
router.register("events", EventViewSet, basename="events")

urlpatterns = [
    path("", include(router.urls)),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/register-developer/", RegisterDeveloperView.as_view(), name="register-developer"),
    path("game-files/<int:pk>/download/", GameFileDownloadView.as_view(), name="game-file-download"),
    path("voting/current/", VotingView.as_view(), name="voting-current"),
    path("voting/vote/", VotingView.as_view(), name="voting-vote"),
    path("newsletter/", NewsletterView.as_view(), name="newsletter"),
    path("data-folders/", DataFolderView.as_view(), name="data-folders"),
    path("data-folders/share/", ShareFolderView.as_view(), name="data-folder-share"),
    path("data-folders/files/", DataFolderFileView.as_view(), name="data-folder-files"),
    path("data-folders/files/<int:pk>/", DataFolderFileView.as_view(), name="data-folder-file-detail"),
    path("data-folders/files/<int:pk>/download/", DataFolderFileDownloadView.as_view(), name="data-folder-file-download"),
]
