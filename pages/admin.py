from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from .models import AudioContent, Page, PageContent, VideoContent


class PageContentInline(GenericTabularInline):
    model = PageContent
    extra = 1
    fields = ("content_type", "object_id", "position")
    ordering = ("position",)


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    search_fields = ("^title",)
    inlines = [PageContentInline]


@admin.register(VideoContent)
class VideoContentAdmin(admin.ModelAdmin):
    search_fields = ("^title",)


@admin.register(AudioContent)
class AudioContentAdmin(admin.ModelAdmin):
    search_fields = ("^title",)
