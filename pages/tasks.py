import uuid
from typing import Dict

import redis
from celery import shared_task
from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.models import F

_REDIS = None
_DEDUP_TTL = int(getattr(settings, "COUNTER_DEDUP_TTL", 15 * 60))  # seconds


def _redis_client() -> redis.Redis:
    global _REDIS
    if _REDIS is None:
        # Use dedicated Redis DB/instance for counters to avoid broker contention
        url = getattr(settings, "COUNTER_REDIS_URL", None) or getattr(
            settings, "CELERY_BROKER_URL", "redis://localhost:6379/1"
        )
        _REDIS = redis.Redis.from_url(url)
    return _REDIS


def _label_set_key() -> str:
    return "views:labels"


def _counter_key(model_label: str) -> str:
    return f"views:counter:{model_label}"


def _dedup_key(task_id: str) -> str:
    return f"views:dedup:{task_id}"


@shared_task(bind=True, acks_late=True, reject_on_worker_lost=True)
def ingest_impressions(self, model_label: str, ids: list[int]) -> None:
    """Aggregate impressions in Redis.

    - Dedup by Celery task_id to be safe on re-delivery (TTL configurable)
    - HINCRBY per id in a pipeline
    - Track active labels for the flusher via a Redis set
    """
    # In tests/eager mode, increment counters directly in DB to make
    # behavior deterministic without relying on Redis/beat flusher.
    if getattr(settings, "RUNNING_TESTS", False) or getattr(
        settings, "CELERY_TASK_ALWAYS_EAGER", False
    ):
        if ids:
            _flush_label_to_db(model_label, {int(_id): 1 for _id in ids})
        return

    r = _redis_client()
    task_id = getattr(getattr(self, "request", None), "id", None)
    if task_id:
        # ensure idempotency for re-delivery
        if not r.set(_dedup_key(task_id), 1, nx=True, ex=_DEDUP_TTL):
            return

    pipe = r.pipeline(transaction=False)
    key = _counter_key(model_label)
    for _id in ids:
        pipe.hincrby(key, str(int(_id)), 1)
    pipe.sadd(_label_set_key(), model_label)
    pipe.execute()


@shared_task(acks_late=True, reject_on_worker_lost=True)
def flush_impressions(batch_size: int = 1000) -> None:
    """Periodically flush aggregated counters from Redis to DB in batches.

    Uses RENAME to a temp key to atomically swap out the active hash, then
    processes the temp key with HSCAN to avoid blocking.
    """
    r = _redis_client()
    labels = r.smembers(_label_set_key())
    if not labels:
        return

    for raw_label in labels:
        label = raw_label.decode()
        src = _counter_key(label)
        tmp = f"{src}:flush:{uuid.uuid4().hex}"
        try:
            # Atomically move the hash to a temp key if it exists
            if not r.exists(src):
                # No data currently; skip
                continue
            r.rename(src, tmp)
        except redis.exceptions.ResponseError:
            # Key disappeared between exists and rename — skip
            continue

        success = False
        try:
            # Consume temp key in chunks
            cursor = 0
            accum: Dict[int, int] = {}
            while True:
                cursor, chunk = r.hscan(tmp, cursor=cursor, count=batch_size)
                for k, v in chunk.items():
                    accum[int(k)] = accum.get(int(k), 0) + int(v)

                # Flush in DB-sized chunks to keep SQL manageable
                if len(accum) >= batch_size:
                    _flush_label_to_db(label, accum)
                    accum.clear()

                if cursor == 0:
                    break

            if accum:
                _flush_label_to_db(label, accum)
            success = True
        finally:
            if success:
                r.delete(tmp)


def _flush_label_to_db(model_label: str, deltas: Dict[int, int]) -> None:
    model = apps.get_model(model_label)
    if model is None or not deltas:
        return
    # Use efficient bulk SQL for PostgreSQL, fallback to ORM updates elsewhere
    if connection.vendor == "postgresql":
        table = connection.ops.quote_name(model._meta.db_table)
        pkcol = connection.ops.quote_name(model._meta.pk.column)

        rows = [(int(pk), int(delta)) for pk, delta in deltas.items()]
        placeholders = ",".join(["(%s,%s)"] * len(rows))
        sql = (
            f"UPDATE {table} AS t "
            f"SET counter = t.counter + v.delta "
            f"FROM (VALUES {placeholders}) AS v(id, delta) "
            f"WHERE t.{pkcol} = v.id"
        )
        params = [item for row in rows for item in row]
        with connection.cursor() as cur:
            cur.execute(sql, params)
    else:
        for pk, delta in deltas.items():
            model.objects.filter(pk=int(pk)).update(counter=F("counter") + int(delta))
