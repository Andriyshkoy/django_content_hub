from celery import shared_task
from django.apps import apps
from django.db.models import F


@shared_task
def increment_counters(model_label: str, ids: list[int]) -> None:
    model = apps.get_model(model_label)
    if model is None:
        return
    model.objects.filter(id__in=ids).update(counter=F("counter") + 1)
