from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, VerifyMismatchError
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.hashers import check_password as django_check_password
from django.db import models


class DeveloperManager(BaseUserManager):
    def create_user(self, username: str, email: str, password: str | None = None, **extra_fields):
        if not username:
            raise ValueError("Username is required")
        if not email:
            raise ValueError("Email is required")
        user = self.model(username=username, email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username: str, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_admin", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(username, email, password, **extra_fields)


class Developer(AbstractBaseUser):
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=100, unique=True)
    full_name = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = DeveloperManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "developers"

    @property
    def is_staff(self) -> bool:
        return self.is_admin

    @property
    def is_superuser(self) -> bool:
        return self.is_admin

    def has_perm(self, perm, obj=None) -> bool:
        return self.is_active and self.is_admin

    def has_module_perms(self, app_label) -> bool:
        return self.is_active and self.is_admin

    def check_password(self, raw_password: str) -> bool:
        if django_check_password(raw_password, self.password):
            return True
        if self.password and self.password.startswith("$argon2"):
            try:
                return PasswordHasher().verify(self.password, raw_password)
            except (VerifyMismatchError, Argon2Error):
                return False
        return False

    def __str__(self) -> str:
        return self.username


class Game(models.Model):
    STATUS_RELEASED = "Released"
    STATUS_UPCOMING = "Upcoming"
    STATUS_DEVELOPMENT = "In Development"
    STATUS_CHOICES = [
        (STATUS_RELEASED, "Released"),
        (STATUS_UPCOMING, "Upcoming"),
        (STATUS_DEVELOPMENT, "In Development"),
    ]

    developer = models.ForeignKey(Developer, on_delete=models.CASCADE, related_name="games")
    title = models.CharField(max_length=200)
    description = models.TextField()
    genre = models.CharField(max_length=50)
    release_date = models.DateField()
    status = models.CharField(max_length=32, choices=STATUS_CHOICES)
    platforms = models.JSONField(default=list, blank=True)
    image_path = models.CharField(max_length=500)
    banner_path = models.CharField(max_length=500, blank=True, null=True)
    game_file_path = models.CharField(max_length=500, blank=True, null=True)
    game_link = models.URLField(max_length=500, blank=True, null=True)
    changelog = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    wishlist_count = models.IntegerField(default=0)
    download_count = models.IntegerField(default=0)
    play_count = models.IntegerField(default=0)
    view_count = models.IntegerField(default=0)

    class Meta:
        db_table = "games"
        indexes = [
            models.Index(fields=["developer"]),
            models.Index(fields=["genre"]),
            models.Index(fields=["status"]),
            models.Index(fields=["release_date"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return self.title


class GameFile(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="files")
    os_type = models.CharField(max_length=50)
    device_type = models.CharField(max_length=50, blank=True, null=True)
    file_path = models.CharField(max_length=500)
    original_file_size = models.BigIntegerField(blank=True, null=True)
    compressed_file_path = models.CharField(max_length=500, blank=True, null=True)
    is_compressed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "game_files"
        indexes = [
            models.Index(fields=["game"]),
            models.Index(fields=["os_type"]),
            models.Index(fields=["device_type"]),
        ]


class NewsletterSubscriber(models.Model):
    email = models.EmailField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    unsubscribe_token = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "newsletter_subscribers"


class GameWishlist(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="wishlist_entries")
    name = models.CharField(max_length=100)
    email = models.EmailField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "game_wishlist"
        constraints = [
            models.UniqueConstraint(fields=["game", "email"], name="unique_wishlist_entry"),
        ]
        indexes = [models.Index(fields=["game"])]


class GameStatistic(models.Model):
    TYPE_DOWNLOAD = "download"
    TYPE_PLAY = "play"
    TYPE_VIEW = "view"
    TYPE_CHOICES = [(TYPE_DOWNLOAD, "Download"), (TYPE_PLAY, "Play"), (TYPE_VIEW, "View")]

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="statistics")
    statistic_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    user_ip = models.CharField(max_length=45, blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "game_statistics"
        indexes = [models.Index(fields=["game"]), models.Index(fields=["statistic_type"])]


class DataFolder(models.Model):
    parent = models.ForeignKey("self", on_delete=models.CASCADE, blank=True, null=True, related_name="children")
    owner = models.ForeignKey(Developer, on_delete=models.CASCADE, related_name="folders")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "data_folders"
        indexes = [models.Index(fields=["owner"]), models.Index(fields=["parent"])]


class DataFolderFile(models.Model):
    folder = models.ForeignKey(DataFolder, on_delete=models.CASCADE, blank=True, null=True, related_name="files")
    uploader = models.ForeignKey(Developer, on_delete=models.CASCADE, related_name="data_files")
    filename = models.CharField(max_length=255, blank=True, default="")
    original_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_size = models.BigIntegerField(blank=True, null=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    is_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "data_folder_files"
        indexes = [models.Index(fields=["folder"]), models.Index(fields=["uploader"])]


class SharedAccess(models.Model):
    RESOURCE_FOLDER = "folder"
    RESOURCE_FILE = "file"
    PERMISSION_READ = "read"
    PERMISSION_WRITE = "write"

    resource_type = models.CharField(max_length=16, choices=[(RESOURCE_FOLDER, "Folder"), (RESOURCE_FILE, "File")])
    resource_id = models.IntegerField()
    granted_to_user = models.ForeignKey(Developer, on_delete=models.CASCADE, related_name="shared_with_me")
    granted_by_user = models.ForeignKey(Developer, on_delete=models.CASCADE, related_name="shares_granted")
    permission_level = models.CharField(max_length=16, choices=[(PERMISSION_READ, "Read"), (PERMISSION_WRITE, "Write")], default=PERMISSION_READ)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "shared_access"


class UserPreference(models.Model):
    user = models.OneToOneField(Developer, on_delete=models.CASCADE, related_name="preferences")
    language_code = models.CharField(max_length=10, default="en")
    theme_preference = models.CharField(max_length=20, default="light")
    notification_preferences = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "user_preferences"


class SystemLog(models.Model):
    log_level = models.CharField(max_length=16, default="info")
    message = models.TextField()
    context = models.JSONField(default=dict, blank=True)
    user = models.ForeignKey(Developer, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "system_logs"


class GameVote(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="votes")
    voter = models.ForeignKey(Developer, on_delete=models.CASCADE, related_name="game_votes")
    vote_month = models.IntegerField()
    vote_year = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "game_votes"
        constraints = [
            models.UniqueConstraint(fields=["voter", "game", "vote_month", "vote_year"], name="unique_vote_per_user_per_month"),
        ]
        indexes = [models.Index(fields=["vote_month", "vote_year"]), models.Index(fields=["game"])]


class GameOfMonth(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name="monthly_rankings")
    vote_month = models.IntegerField()
    vote_year = models.IntegerField()
    total_votes = models.IntegerField(default=0)
    rank_position = models.IntegerField(default=0)
    is_winner = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "game_of_month"
        constraints = [
            models.UniqueConstraint(fields=["game", "vote_month", "vote_year"], name="unique_game_per_month"),
        ]
        indexes = [models.Index(fields=["vote_month", "vote_year"])]


class Event(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    event_date = models.DateField()
    event_time = models.TimeField()
    location = models.CharField(max_length=255, blank=True, null=True)
    creator = models.ForeignKey(Developer, on_delete=models.CASCADE, related_name="events")
    max_attendees = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "events"
        indexes = [models.Index(fields=["event_date"]), models.Index(fields=["creator"])]


class EventAttendee(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="attendees")
    user = models.ForeignKey(Developer, on_delete=models.CASCADE, related_name="event_attendance")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "event_attendees"
        constraints = [models.UniqueConstraint(fields=["event", "user"], name="unique_event_user")]
        indexes = [models.Index(fields=["event"]), models.Index(fields=["user"])]
