from django.contrib import admin
from .models import Person, Rating, Comment, Category

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at',)

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'average_rating', 'total_ratings', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('category', 'created_at')
    autocomplete_fields = ['category']

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('person', 'user', 'score', 'created_at')
    list_filter = ('score', 'created_at')
    search_fields = ('person__name', 'user__username')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('person', 'user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('person__name', 'user__username', 'content')
