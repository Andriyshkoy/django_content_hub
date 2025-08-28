import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from pages.models import AudioContent, Page, PageContent, VideoContent


@pytest.mark.django_db
def test_page_list_returns_pages():
    page = Page.objects.create(title="Page 1")
    client = APIClient()
    url = reverse("page-list")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.data["results"][0]["title"] == page.title
    assert "url" in resp.data["results"][0]


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_page_detail_returns_contents_and_increments_counters():
    page = Page.objects.create(title="P")
    video = VideoContent.objects.create(
        title="V", file_url="http://example.com/v.mp4", subtitles_url=""
    )
    audio = AudioContent.objects.create(title="A", text="hello")
    ct_video = ContentType.objects.get_for_model(VideoContent)
    ct_audio = ContentType.objects.get_for_model(AudioContent)
    PageContent.objects.create(
        page=page, content_type=ct_video, object_id=video.id, position=1
    )
    PageContent.objects.create(
        page=page, content_type=ct_audio, object_id=audio.id, position=2
    )

    client = APIClient()
    url = reverse("page-detail", args=[page.id])
    resp = client.get(url)
    assert resp.status_code == 200
    assert len(resp.data["contents"]) == 2
    assert resp.data["contents"][0]["type"] == "video"
    assert resp.data["contents"][1]["type"] == "audio"
    video.refresh_from_db()
    audio.refresh_from_db()
    assert video.counter == 1
    assert audio.counter == 1
