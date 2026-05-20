from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import (
    DataFolder,
    DataFolderFile,
    Developer,
    Event,
    Game,
    GameFile,
    GameWishlist,
    UserPreference,
)
from .uploading import media_url


class DeveloperSerializer(serializers.ModelSerializer):
    class Meta:
        model = Developer
        fields = ["id", "username", "email", "full_name", "is_active", "is_admin", "created_at", "last_login"]
        read_only_fields = ["id", "created_at", "last_login"]


class RegisterDeveloperSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, validators=[validate_password])

    class Meta:
        model = Developer
        fields = ["id", "username", "email", "full_name", "password", "is_admin"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = Developer(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = ["language_code", "theme_preference", "notification_preferences"]


class GameFileSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    size = serializers.IntegerField(source="original_file_size", read_only=True)

    class Meta:
        model = GameFile
        fields = [
            "id",
            "os_type",
            "device_type",
            "file_path",
            "compressed_file_path",
            "size",
            "is_compressed",
            "download_url",
        ]

    def get_download_url(self, obj):
        request = self.context.get("request")
        if not request:
            return f"/api/game-files/{obj.id}/download/"
        return request.build_absolute_uri(f"/api/game-files/{obj.id}/download/")


class GameSerializer(serializers.ModelSerializer):
    developer_name = serializers.CharField(source="developer.username", read_only=True)
    files = GameFileSerializer(many=True, read_only=True)
    image_url = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()
    vote_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Game
        fields = [
            "id",
            "developer",
            "developer_name",
            "title",
            "description",
            "genre",
            "release_date",
            "status",
            "platforms",
            "image_path",
            "image_url",
            "banner_path",
            "banner_url",
            "game_file_path",
            "game_link",
            "changelog",
            "created_at",
            "updated_at",
            "wishlist_count",
            "download_count",
            "play_count",
            "view_count",
            "vote_count",
            "files",
        ]
        read_only_fields = [
            "id",
            "developer",
            "created_at",
            "updated_at",
            "wishlist_count",
            "download_count",
            "play_count",
            "view_count",
        ]

    def get_image_url(self, obj):
        return media_url(self.context["request"], obj.image_path)

    def get_banner_url(self, obj):
        return media_url(self.context["request"], obj.banner_path)


class WishlistSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameWishlist
        fields = ["id", "game", "name", "email", "created_at"]
        read_only_fields = ["id", "game", "created_at"]


class DataFolderSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = DataFolder
        fields = ["id", "parent", "owner", "owner_name", "name", "description", "is_shared", "created_at", "updated_at"]
        read_only_fields = ["id", "owner", "owner_name", "created_at", "updated_at"]


class DataFolderFileSerializer(serializers.ModelSerializer):
    uploader_name = serializers.CharField(source="uploader.username", read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = DataFolderFile
        fields = [
            "id",
            "folder",
            "uploader",
            "uploader_name",
            "filename",
            "original_name",
            "file_path",
            "file_size",
            "mime_type",
            "is_shared",
            "download_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "uploader", "uploader_name", "file_path", "file_size", "mime_type", "created_at", "updated_at"]

    def get_download_url(self, obj):
        request = self.context.get("request")
        if not request:
            return f"/api/data-folders/files/{obj.id}/download/"
        return request.build_absolute_uri(f"/api/data-folders/files/{obj.id}/download/")


class EventSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="creator.username", read_only=True)
    attendee_count = serializers.IntegerField(read_only=True, default=0)
    is_attending = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "event_date",
            "event_time",
            "location",
            "creator",
            "creator_name",
            "max_attendees",
            "attendee_count",
            "is_attending",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "creator", "creator_name", "attendee_count", "created_at", "updated_at"]

    def get_is_attending(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.attendees.filter(user=request.user).exists())
