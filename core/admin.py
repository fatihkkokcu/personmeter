from django.contrib import admin
from django.utils import timezone

from .models import Category, Comment, ModerationLog, Person, Rating, Report, UserProfile

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at',)

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_hidden', 'average_rating', 'total_ratings', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('is_hidden', 'category', 'created_at')
    autocomplete_fields = ['category']

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('person', 'user', 'score', 'created_at')
    list_filter = ('score', 'created_at')
    search_fields = ('person__name', 'user__username')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('person', 'user', 'is_hidden', 'created_at')
    list_filter = ('is_hidden', 'created_at')
    search_fields = ('person__name', 'user__username', 'content')


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "target_type",
        "target_display",
        "reporter",
        "reason",
        "status",
        "created_at",
        "reviewed_by",
    )
    list_filter = ("status", "reason", "created_at")
    search_fields = (
        "reporter__username",
        "person__name",
        "comment__content",
        "details",
        "resolution_notes",
    )
    readonly_fields = ("created_at", "reviewed_at", "target_type", "target_display")
    autocomplete_fields = ("reporter", "person", "comment", "reviewed_by")
    actions = ("mark_reviewed", "mark_dismissed", "mark_actioned")

    @admin.action(description="Mark selected reports as reviewed")
    def mark_reviewed(self, request, queryset):
        queryset.update(
            status=Report.STATUS_REVIEWED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

    @admin.action(description="Mark selected reports as dismissed")
    def mark_dismissed(self, request, queryset):
        queryset.update(
            status=Report.STATUS_DISMISSED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

    @admin.action(description="Mark selected reports as actioned")
    def mark_actioned(self, request, queryset):
        queryset.update(
            status=Report.STATUS_ACTIONED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "moderation_status",
        "warning_count",
        "strike_count",
        "muted_until",
        "suspended_until",
        "banned_at",
    )
    list_filter = ("moderation_status", "muted_until", "suspended_until", "banned_at")
    search_fields = ("user__username", "user__email", "moderation_note")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "action",
        "actor",
        "target_user",
        "person",
        "comment",
        "report",
        "created_at",
    )
    list_filter = ("action", "created_at")
    search_fields = (
        "details",
        "actor__username",
        "target_user__username",
        "person__name",
        "comment__content",
    )
    autocomplete_fields = ("actor", "target_user", "person", "comment", "report")
