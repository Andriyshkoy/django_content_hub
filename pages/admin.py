from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from .forms import PageContentInlineForm, get_allowed_content_models
from .models import AudioContent, Page, PageContent, VideoContent


class PageContentInline(admin.TabularInline):
    model = PageContent
    extra = 1
    form = PageContentInlineForm
    fields = ("content_item",)
    ordering = ("id",)


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    search_fields = ("^title",)
    inlines = [PageContentInline]

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path(
                "content-autocomplete/",
                self.admin_site.admin_view(self.content_autocomplete),
                name="pages_page_content_autocomplete",
            )
        ]
        return extra + urls

    def content_autocomplete(self, request):
        term = request.GET.get("term", "").strip()
        page = int(request.GET.get("page") or 1)
        page_size = 20
        start = (page - 1) * page_size
        end = start + page_size

        results = []
        total_count = 0
        for m in get_allowed_content_models():
            qs = m.objects.all()
            # Prefer searching by ContentBase.title
            try:
                qs.model._meta.get_field("title")
                if term:
                    qs = qs.filter(title__icontains=term)
            except Exception:
                if term:
                    qs = qs.none()
            count = qs.count()
            total_count += count
            if count == 0:
                continue
            # Collect slice that falls into [start:end] over the cumulative list
            if len(results) >= end:
                continue
            # Compute remaining capacity
            need = end - len(results)
            for obj in qs[:need]:
                value = f"{m._meta.app_label}.{m._meta.model_name}:{obj.pk}"
                label = f"{m._meta.verbose_name.title()} | {obj}"
                results.append({"id": value, "text": label})
                if len(results) >= end:
                    break

        page_results = results[start:end]
        more = total_count > end
        return JsonResponse({"results": page_results, "pagination": {"more": more}})


@admin.register(VideoContent)
class VideoContentAdmin(admin.ModelAdmin):
    search_fields = ("^title",)


@admin.register(AudioContent)
class AudioContentAdmin(admin.ModelAdmin):
    search_fields = ("^title",)
