from django.contrib import admin

from .models import (
    DataFolder,
    DataFolderFile,
    Developer,
    Event,
    Game,
    GameFile,
    GameVote,
    GameWishlist,
    NewsletterSubscriber,
)


@admin.register(Developer)
class DeveloperAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "full_name", "is_active", "is_admin", "created_at", "last_login")
    search_fields = ("username", "email", "full_name")
    list_filter = ("is_active", "is_admin")


class GameFileInline(admin.TabularInline):
    model = GameFile
    extra = 0


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ("title", "developer", "genre", "status", "release_date", "download_count", "view_count")
    search_fields = ("title", "description", "developer__username")
    list_filter = ("genre", "status", "release_date")
    inlines = [GameFileInline]


admin.site.register(GameWishlist)
admin.site.register(GameVote)
admin.site.register(NewsletterSubscriber)
admin.site.register(DataFolder)
admin.site.register(DataFolderFile)
admin.site.register(Event)
