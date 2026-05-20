from __future__ import annotations

from datetime import date
from itertools import zip_longest
import gzip
import secrets

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import update_last_login
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.http import FileResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    DataFolder,
    DataFolderFile,
    Developer,
    Event,
    EventAttendee,
    Game,
    GameFile,
    GameStatistic,
    GameVote,
    GameWishlist,
    NewsletterSubscriber,
    SharedAccess,
    UserPreference,
)
from .serializers import (
    DataFolderFileSerializer,
    DataFolderSerializer,
    DeveloperSerializer,
    EventSerializer,
    GameSerializer,
    RegisterDeveloperSerializer,
    UserPreferenceSerializer,
    WishlistSerializer,
)
from .uploading import (
    content_type_for,
    delete_many,
    delete_media_path,
    gzip_file,
    normalize_relative_path,
    resolve_existing_media_path,
    save_uploaded_file,
    validate_data_file,
    validate_game_file,
    validate_image,
)


def qd_list(data, *names: str) -> list:
    for name in names:
        if hasattr(data, "getlist"):
            values = [value for value in data.getlist(name) if value not in ("", None)]
            if values:
                return values
        value = data.get(name)
        if value not in ("", None):
            return value if isinstance(value, list) else [value]
    return []


def parse_platforms(data) -> list[str]:
    values = qd_list(data, "platforms[]", "platforms")
    if len(values) == 1 and isinstance(values[0], str):
        value = values[0].strip()
        if value.startswith("[") and value.endswith("]"):
            import json

            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass
        if "," in value:
            return [part.strip() for part in value.split(",") if part.strip()]
    return [str(value).strip() for value in values if str(value).strip()]


def get_uploaded_files(request, *names: str) -> list:
    for name in names:
        files = request.FILES.getlist(name)
        if files:
            return files
    return []


def request_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def record_game_stat(game: Game, statistic_type: str, request) -> None:
    if statistic_type not in {"download", "play", "view"}:
        return
    GameStatistic.objects.create(
        game=game,
        statistic_type=statistic_type,
        user_ip=request_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )
    Game.objects.filter(pk=game.pk).update(**{f"{statistic_type}_count": F(f"{statistic_type}_count") + 1})


def current_month_year() -> tuple[int, int]:
    today = timezone.localdate()
    return today.month, today.year


class IsAdminUser(IsAuthenticated):
    def has_permission(self, request, view):
        return bool(super().has_permission(request, view) and request.user.is_admin)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        identifier = (request.data.get("username") or request.data.get("email") or "").strip()
        password = request.data.get("password") or ""
        if not identifier or not password:
            return Response({"detail": "Username/email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        user = Developer.objects.filter(Q(username=identifier) | Q(email=identifier), is_active=True).first()
        if not user or not user.check_password(password):
            return Response({"detail": "Invalid username or password."}, status=status.HTTP_401_UNAUTHORIZED)

        update_last_login(None, user)
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": DeveloperSerializer(user).data,
            }
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        preference, _ = UserPreference.objects.get_or_create(user=request.user)
        return Response(
            {
                "user": DeveloperSerializer(request.user).data,
                "preferences": UserPreferenceSerializer(preference).data,
            }
        )

    def patch(self, request):
        preference, _ = UserPreference.objects.get_or_create(user=request.user)
        serializer = UserPreferenceSerializer(preference, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class RegisterDeveloperView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = RegisterDeveloperSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save(is_active=True)
        return Response(DeveloperSerializer(user).data, status=status.HTTP_201_CREATED)


class DeveloperAdminViewSet(viewsets.ModelViewSet):
    serializer_class = DeveloperSerializer
    queryset = Developer.objects.order_by("-is_admin", "-created_at")
    permission_classes = [IsAdminUser]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    @action(detail=True, methods=["post"])
    def set_admin(self, request, pk=None):
        user = self.get_object()
        user.is_admin = bool(request.data.get("is_admin"))
        user.save(update_fields=["is_admin", "updated_at"])
        return Response(DeveloperSerializer(user).data)


class GameViewSet(viewsets.ModelViewSet):
    serializer_class = GameSerializer

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [AllowAny()]
        if self.action in {"wishlist", "statistics"}:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        month, year = current_month_year()
        queryset = (
            Game.objects.select_related("developer")
            .prefetch_related("files")
            .annotate(vote_count=Count("votes", filter=Q(votes__vote_month=month, votes__vote_year=year)))
            .order_by("-created_at")
        )
        genre = self.request.query_params.get("genre")
        status_filter = self.request.query_params.get("status")
        search = self.request.query_params.get("search")
        mine = self.request.query_params.get("mine")
        if genre:
            queryset = queryset.filter(genre=genre)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if search:
            queryset = queryset.filter(Q(title__icontains=search) | Q(description__icontains=search))
        if mine and self.request.user.is_authenticated:
            queryset = queryset.filter(developer=self.request.user)
        return queryset

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        record_game_stat(instance, "view", request)
        instance.refresh_from_db()
        return Response(self.get_serializer(instance).data)

    def _validate_owner(self, request, game: Game) -> None:
        if not request.user.is_authenticated or (game.developer_id != request.user.id and not request.user.is_admin):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You do not have permission to modify this game.")

    def _create_game_files(self, request, game: Game, replace_existing: bool = False) -> tuple[int, list[str]]:
        files = get_uploaded_files(request, "game_file[]", "game_file", "files[]", "files")
        os_types = qd_list(request.data, "os_type[]", "os_type", "os_types[]", "os_types")
        device_types = qd_list(request.data, "device_type[]", "device_type", "device_types[]", "device_types")
        errors: list[str] = []
        uploaded = 0

        if replace_existing:
            for game_file in game.files.all():
                delete_many([game_file.file_path, game_file.compressed_file_path])
            game.files.all().delete()

        for index, (upload, os_type, device_type) in enumerate(zip_longest(files, os_types, device_types, fillvalue="")):
            os_type = str(os_type or "").strip()
            device_type = str(device_type or "").strip() or None
            if not upload and not os_type:
                continue
            if not upload or not os_type:
                errors.append(f"OS file #{index + 1}: both operating system and file are required.")
                continue
            try:
                validate_game_file(upload)
                saved_path = save_uploaded_file(upload, "games", f"game_{game.id}_{os_type.lower().replace(' ', '-')}")
                compressed_path = gzip_file(saved_path, f"game_{game.id}_{os_type.lower().replace(' ', '-')}_compressed")
                GameFile.objects.create(
                    game=game,
                    os_type=os_type,
                    device_type=device_type,
                    file_path=saved_path,
                    original_file_size=upload.size,
                    compressed_file_path=compressed_path,
                    is_compressed=True,
                )
                uploaded += 1
            except DjangoValidationError as exc:
                errors.append(f"{os_type or 'Unknown OS'}: {' '.join(exc.messages)}")
            except Exception as exc:
                errors.append(f"{os_type or 'Unknown OS'}: {exc}")
        return uploaded, errors

    def create(self, request, *args, **kwargs):
        image = request.FILES.get("image") or request.FILES.get("thumbnail")
        banner = request.FILES.get("banner")
        game_files = get_uploaded_files(request, "game_file[]", "game_file", "files[]", "files")
        game_link = (request.data.get("game_link") or "").strip() or None
        platforms = parse_platforms(request.data)

        required = ["title", "genre", "description", "release_date", "status"]
        missing = [field for field in required if not str(request.data.get(field, "")).strip()]
        if missing:
            return Response({"detail": f"Missing required fields: {', '.join(missing)}"}, status=status.HTTP_400_BAD_REQUEST)
        if not platforms:
            return Response({"detail": "Select at least one platform."}, status=status.HTTP_400_BAD_REQUEST)
        if bool(game_files) == bool(game_link):
            return Response({"detail": "Provide either OS-specific files or a game link, not both."}, status=status.HTTP_400_BAD_REQUEST)

        saved_paths: list[str] = []
        try:
            validate_image(image)
            if banner:
                validate_image(banner, required=False)
            image_path = save_uploaded_file(image, "thumbnails", "game")
            saved_paths.append(image_path)
            banner_path = None
            if banner:
                banner_path = save_uploaded_file(banner, "thumbnails", "banner")
                saved_paths.append(banner_path)

            with transaction.atomic():
                game = Game.objects.create(
                    developer=request.user,
                    title=request.data["title"].strip(),
                    description=request.data["description"].strip(),
                    genre=request.data["genre"].strip(),
                    release_date=request.data["release_date"],
                    status=request.data["status"].strip(),
                    platforms=platforms,
                    image_path=image_path,
                    banner_path=banner_path,
                    game_link=game_link,
                    changelog=(request.data.get("changelog") or "").strip() or None,
                )
                warnings: list[str] = []
                if game_files:
                    uploaded_count, warnings = self._create_game_files(request, game)
                    if uploaded_count == 0:
                        raise DjangoValidationError(warnings or ["No valid OS-specific files were uploaded."])
            serializer = self.get_serializer(game)
            response_status = status.HTTP_201_CREATED if not warnings else status.HTTP_207_MULTI_STATUS
            return Response({"game": serializer.data, "warnings": warnings}, status=response_status)
        except DjangoValidationError as exc:
            delete_many(saved_paths)
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            delete_many(saved_paths)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        game = self.get_object()
        self._validate_owner(request, game)

        game_files = get_uploaded_files(request, "game_file[]", "game_file", "files[]", "files")
        game_link = (request.data.get("game_link") or "").strip() or None
        if game_files and game_link:
            return Response({"detail": "Provide either OS-specific files or a game link, not both."}, status=status.HTTP_400_BAD_REQUEST)

        saved_paths: list[str] = []
        try:
            for field in ["title", "description", "genre", "release_date", "status", "changelog"]:
                if field in request.data:
                    setattr(game, field, request.data.get(field) or None)
            platforms = parse_platforms(request.data)
            if platforms:
                game.platforms = platforms
            image = request.FILES.get("image") or request.FILES.get("thumbnail")
            banner = request.FILES.get("banner")
            if image:
                validate_image(image)
                old_path = game.image_path
                game.image_path = save_uploaded_file(image, "thumbnails", "game")
                saved_paths.append(game.image_path)
                delete_media_path(old_path)
            if banner:
                validate_image(banner, required=False)
                old_path = game.banner_path
                game.banner_path = save_uploaded_file(banner, "thumbnails", "banner")
                saved_paths.append(game.banner_path)
                delete_media_path(old_path)
            if "game_link" in request.data or game_files:
                game.game_link = game_link
                game.game_file_path = None
            game.save()

            warnings: list[str] = []
            if game_files:
                uploaded_count, warnings = self._create_game_files(request, game, replace_existing=True)
                if uploaded_count == 0:
                    raise DjangoValidationError(warnings or ["No valid OS-specific files were uploaded."])
            return Response({"game": self.get_serializer(game).data, "warnings": warnings})
        except DjangoValidationError as exc:
            delete_many(saved_paths)
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        game = self.get_object()
        self._validate_owner(request, game)
        paths = [game.image_path, game.banner_path, game.game_file_path]
        for game_file in game.files.all():
            paths.extend([game_file.file_path, game_file.compressed_file_path])
        game.delete()
        delete_many(paths)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], permission_classes=[AllowAny])
    def statistics(self, request, pk=None):
        game = self.get_object()
        statistic_type = request.data.get("action_type") or request.data.get("statistic_type")
        if statistic_type not in {"download", "play", "view"}:
            return Response({"detail": "Invalid statistic type."}, status=status.HTTP_400_BAD_REQUEST)
        record_game_stat(game, statistic_type, request)
        return Response({"success": True})

    @action(detail=True, methods=["post"], permission_classes=[AllowAny])
    def wishlist(self, request, pk=None):
        game = self.get_object()
        serializer = WishlistSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                entry = serializer.save(game=game)
                Game.objects.filter(pk=game.pk).update(wishlist_count=F("wishlist_count") + 1)
        except IntegrityError:
            return Response({"detail": "This email is already on the wishlist for this game."}, status=status.HTTP_409_CONFLICT)
        return Response(WishlistSerializer(entry).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def wishlist_entries(self, request, pk=None):
        game = self.get_object()
        self._validate_owner(request, game)
        return Response(WishlistSerializer(game.wishlist_entries.order_by("-created_at"), many=True).data)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def download(self, request, pk=None):
        game = self.get_object()
        if not game.game_file_path:
            return Response({"detail": "No legacy game file is available."}, status=status.HTTP_404_NOT_FOUND)
        path = resolve_existing_media_path(game.game_file_path)
        if not path:
            return Response({"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND)
        record_game_stat(game, "download", request)
        return FileResponse(path.open("rb"), as_attachment=True, filename=path.name, content_type=content_type_for(str(path)))


class GameFileDownloadView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk: int):
        game_file = get_object_or_404(GameFile.objects.select_related("game"), pk=pk)
        relative_path = game_file.compressed_file_path if game_file.is_compressed else game_file.file_path
        path = resolve_existing_media_path(relative_path)
        if not path:
            return Response({"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND)
        record_game_stat(game_file.game, "download", request)
        filename = normalize_relative_path(game_file.file_path).rsplit("/", 1)[-1] or path.name.removesuffix(".gz")
        if game_file.is_compressed:
            def stream():
                with gzip.open(path, "rb") as source:
                    while chunk := source.read(1024 * 1024):
                        yield chunk

            return StreamingHttpResponse(
                stream(),
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                content_type="application/octet-stream",
            )
        return FileResponse(path.open("rb"), as_attachment=True, filename=filename, content_type=content_type_for(str(path)))


class VotingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        month, year = current_month_year()
        user_vote = GameVote.objects.filter(voter=request.user, vote_month=month, vote_year=year).first()
        games = (
            Game.objects.select_related("developer")
            .annotate(vote_count=Count("votes", filter=Q(votes__vote_month=month, votes__vote_year=year)))
            .order_by("-vote_count", "-created_at")
        )
        return Response(
            {
                "month": month,
                "year": year,
                "user_vote_game_id": user_vote.game_id if user_vote else None,
                "games": GameSerializer(games, many=True, context={"request": request}).data,
            }
        )

    def post(self, request):
        game = get_object_or_404(Game, pk=request.data.get("game_id"))
        month, year = current_month_year()
        existing_vote = GameVote.objects.filter(voter=request.user, vote_month=month, vote_year=year).first()
        if existing_vote:
            if existing_vote.game_id == game.id:
                return Response({"detail": "You have already voted for this game this month."}, status=status.HTTP_409_CONFLICT)
            existing_vote.game = game
            existing_vote.save(update_fields=["game"])
            return Response({"success": True, "message": "Vote updated successfully."})
        GameVote.objects.create(game=game, voter=request.user, vote_month=month, vote_year=year)
        return Response({"success": True, "message": "Vote cast successfully."}, status=status.HTTP_201_CREATED)


class NewsletterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        if not email or "@" not in email:
            return Response({"detail": "Please enter a valid email address."}, status=status.HTTP_400_BAD_REQUEST)
        token = secrets.token_urlsafe(32)
        subscriber, _ = NewsletterSubscriber.objects.update_or_create(
            email=email,
            defaults={"is_active": True, "unsubscribe_token": token},
        )
        return Response({"success": True, "message": "Thank you for subscribing to our newsletter.", "unsubscribe_token": subscriber.unsubscribe_token})

    def delete(self, request):
        email = (request.data.get("email") or "").strip().lower()
        token = request.data.get("token")
        queryset = NewsletterSubscriber.objects.all()
        if token:
            queryset = queryset.filter(unsubscribe_token=token)
        elif email:
            queryset = queryset.filter(email=email)
        else:
            return Response({"detail": "Email or token is required."}, status=status.HTTP_400_BAD_REQUEST)
        updated = queryset.update(is_active=False)
        if not updated:
            return Response({"detail": "Subscription not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"success": True, "message": "You have been unsubscribed."})


def can_access_folder(user: Developer, folder: DataFolder, write: bool = False) -> bool:
    if folder.owner_id == user.id or user.is_admin:
        return True
    permission_filter = Q(resource_type=SharedAccess.RESOURCE_FOLDER, resource_id=folder.id, granted_to_user=user)
    if write:
        permission_filter &= Q(permission_level=SharedAccess.PERMISSION_WRITE)
    return SharedAccess.objects.filter(permission_filter).exists()


def can_access_file(user: Developer, file: DataFolderFile, write: bool = False) -> bool:
    if file.uploader_id == user.id or user.is_admin:
        return True
    access = SharedAccess.objects.filter(granted_to_user=user).filter(
        Q(resource_type=SharedAccess.RESOURCE_FILE, resource_id=file.id)
        | Q(resource_type=SharedAccess.RESOURCE_FOLDER, resource_id=file.folder_id)
    )
    if write:
        access = access.filter(permission_level=SharedAccess.PERMISSION_WRITE)
    return access.exists()


class DataFolderView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        folder_id = request.query_params.get("folder")
        current_folder = None
        if folder_id:
            current_folder = get_object_or_404(DataFolder, pk=folder_id)
            if not can_access_folder(request.user, current_folder):
                return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        if current_folder:
            folders = DataFolder.objects.filter(parent=current_folder).order_by("name")
            files = DataFolderFile.objects.filter(folder=current_folder).order_by("-created_at")
        else:
            shared_folder_ids = SharedAccess.objects.filter(
                granted_to_user=request.user, resource_type=SharedAccess.RESOURCE_FOLDER
            ).values_list("resource_id", flat=True)
            folders = DataFolder.objects.filter(Q(owner=request.user, parent__isnull=True) | Q(id__in=shared_folder_ids)).distinct().order_by("name")
            files = DataFolderFile.objects.filter(folder__isnull=True, uploader=request.user).order_by("-created_at")

        breadcrumb = []
        cursor = current_folder
        while cursor:
            breadcrumb.insert(0, DataFolderSerializer(cursor, context={"request": request}).data)
            cursor = cursor.parent

        return Response(
            {
                "current_folder": DataFolderSerializer(current_folder, context={"request": request}).data if current_folder else None,
                "breadcrumb": breadcrumb,
                "folders": DataFolderSerializer(folders, many=True, context={"request": request}).data,
                "files": DataFolderFileSerializer(files, many=True, context={"request": request}).data,
            }
        )

    def post(self, request):
        parent = None
        parent_id = request.data.get("parent_id") or request.data.get("parent")
        if parent_id:
            parent = get_object_or_404(DataFolder, pk=parent_id)
            if not can_access_folder(request.user, parent, write=True):
                return Response({"detail": "Write access denied."}, status=status.HTTP_403_FORBIDDEN)
        name = (request.data.get("name") or request.data.get("folder_name") or "").strip()
        if not name:
            return Response({"detail": "Folder name is required."}, status=status.HTTP_400_BAD_REQUEST)
        folder = DataFolder.objects.create(owner=request.user, parent=parent, name=name, description=request.data.get("description") or "")
        return Response(DataFolderSerializer(folder, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def delete(self, request):
        folder = get_object_or_404(DataFolder, pk=request.data.get("id") or request.query_params.get("id"))
        if folder.owner_id != request.user.id and not request.user.is_admin:
            return Response({"detail": "Only the owner can delete this folder."}, status=status.HTTP_403_FORBIDDEN)
        file_paths = []
        for file in DataFolderFile.objects.filter(Q(folder=folder) | Q(folder__parent=folder)):
            file_paths.append(file.file_path)
        folder.delete()
        delete_many(file_paths)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DataFolderFileView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        upload = request.FILES.get("file")
        folder = None
        folder_id = request.data.get("folder_id") or request.data.get("folder")
        if folder_id:
            folder = get_object_or_404(DataFolder, pk=folder_id)
            if not can_access_folder(request.user, folder, write=True):
                return Response({"detail": "Write access denied."}, status=status.HTTP_403_FORBIDDEN)
        try:
            validate_data_file(upload)
            path = save_uploaded_file(upload, "data-folders", "data")
            file = DataFolderFile.objects.create(
                folder=folder,
                uploader=request.user,
                filename=path.rsplit("/", 1)[-1],
                original_name=upload.name,
                file_path=path,
                file_size=upload.size,
                mime_type=getattr(upload, "content_type", "") or content_type_for(upload.name),
            )
            return Response(DataFolderFileSerializer(file, context={"request": request}).data, status=status.HTTP_201_CREATED)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        file = get_object_or_404(DataFolderFile, pk=pk or request.data.get("id") or request.query_params.get("id"))
        if file.uploader_id != request.user.id and not request.user.is_admin:
            return Response({"detail": "Only the uploader can delete this file."}, status=status.HTTP_403_FORBIDDEN)
        path = file.file_path
        file.delete()
        delete_media_path(path)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DataFolderFileDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        file = get_object_or_404(DataFolderFile, pk=pk)
        if not can_access_file(request.user, file):
            return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
        path = resolve_existing_media_path(file.file_path)
        if not path:
            return Response({"detail": "File not found."}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(path.open("rb"), as_attachment=True, filename=file.original_name, content_type=content_type_for(str(path)))


class ShareFolderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        folder = get_object_or_404(DataFolder, pk=request.data.get("folder_id"))
        if folder.owner_id != request.user.id and not request.user.is_admin:
            return Response({"detail": "You do not own this folder."}, status=status.HTTP_403_FORBIDDEN)
        username = (request.data.get("shared_with") or request.data.get("username") or "").strip()
        recipient = get_object_or_404(Developer, username=username, is_active=True)
        permission = request.data.get("permission") or "read"
        if permission not in {SharedAccess.PERMISSION_READ, SharedAccess.PERMISSION_WRITE}:
            return Response({"detail": "Invalid permission."}, status=status.HTTP_400_BAD_REQUEST)
        access, created = SharedAccess.objects.get_or_create(
            resource_type=SharedAccess.RESOURCE_FOLDER,
            resource_id=folder.id,
            granted_to_user=recipient,
            defaults={"granted_by_user": request.user, "permission_level": permission},
        )
        if not created:
            access.permission_level = permission
            access.granted_by_user = request.user
            access.save(update_fields=["permission_level", "granted_by_user"])
        folder.is_shared = True
        folder.save(update_fields=["is_shared", "updated_at"])
        return Response({"success": True, "recipient_username": recipient.username, "permission": permission})


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsAdminUser()]
        if self.action in {"attend", "leave"}:
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_queryset(self):
        return Event.objects.select_related("creator").annotate(attendee_count=Count("attendees")).order_by("event_date", "event_time")

    def list(self, request, *args, **kwargs):
        today = date.today()
        queryset = self.get_queryset()
        return Response(
            {
                "upcoming": self.get_serializer(queryset.filter(event_date__gte=today), many=True).data,
                "past": self.get_serializer(queryset.filter(event_date__lt=today).order_by("-event_date", "-event_time")[:10], many=True).data,
            }
        )

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    @action(detail=True, methods=["post"])
    def attend(self, request, pk=None):
        event = self.get_object()
        if event.max_attendees is not None and event.attendees.count() >= event.max_attendees:
            return Response({"detail": "This event has reached maximum capacity."}, status=status.HTTP_409_CONFLICT)
        EventAttendee.objects.get_or_create(event=event, user=request.user)
        return Response({"success": True})

    @action(detail=True, methods=["post"])
    def leave(self, request, pk=None):
        EventAttendee.objects.filter(event=self.get_object(), user=request.user).delete()
        return Response({"success": True})
