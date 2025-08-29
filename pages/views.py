from collections import defaultdict

from django.db.models import Prefetch
from rest_framework import viewsets
from rest_framework.response import Response

from .models import Page, PageContent
from .serializers import PageDetailSerializer, PageListSerializer
from .tasks import ingest_impressions


class PageViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only API for pages.

    Notes:
    - Uses ``Prefetch`` on the generic relation container; the underlying
      ``GenericForeignKey`` cannot be fully prefetch-optimized by DRF/Django
      out of the box. For large datasets consider model-specific joins or
      explicit relations.
    - On retrieve, impressions are aggregated asynchronously via Celery to
      avoid adding latency to the API response.
    """

    queryset = Page.objects.all().prefetch_related(
        Prefetch(
            "contents",
            queryset=PageContent.objects.select_related("content_type")
            .order_by("id")
            .prefetch_related("content_object"),
        )
    )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PageDetailSerializer
        return PageListSerializer

    def retrieve(self, request, *args, **kwargs):
        page: Page = self.get_object()
        content_map: dict[str, set[int]] = defaultdict(set)
        for pc in page.contents.all():
            label = f"{pc.content_type.app_label}.{pc.content_type.model}"
            content_map[label].add(pc.object_id)
        for label, ids in content_map.items():
            ingest_impressions.delay(label, list(ids))
        return Response(self.get_serializer(page).data)
