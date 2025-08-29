from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Page(models.Model):
    title = models.CharField(max_length=255, db_index=True)

    def __str__(self) -> str:
        return self.title

    class Meta:
        ordering = ["id"]


class ContentBase(models.Model):
    title = models.CharField(max_length=255, db_index=True)
    counter = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.title


class VideoContent(ContentBase):
    file_url = models.URLField()
    subtitles_url = models.URLField(blank=True)


class AudioContent(ContentBase):
    text = models.TextField()


class PageContent(models.Model):
    page = models.ForeignKey(Page, related_name="contents", on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        indexes = [
            models.Index(fields=["page", "position", "id"]),
        ]

    def __str__(self) -> str:
        return f"{self.page} -> {self.content_object}"
