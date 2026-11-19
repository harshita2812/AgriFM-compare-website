import logging
from contextlib import closing

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import HTTPException

from apps.api.db import connect


LOGGER = logging.getLogger(__name__)


def refresh_all_region_weather() -> None:
    from apps.api.main import refresh_weather

    with closing(connect()) as conn:
        region_ids = [row["id"] for row in conn.execute("SELECT id FROM regions").fetchall()]
    for region_id in region_ids:
        try:
            refresh_weather(region_id, 7)
        except HTTPException as error:
            LOGGER.warning("Scheduled weather refresh failed for %s: %s", region_id, error.detail)


def reverify_asset_hashes() -> None:
    from apps.api.asset_inventory import verify_registered_assets

    for detail in verify_registered_assets():
        LOGGER.error("Scheduled asset verification failed: %s", detail)


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        refresh_all_region_weather,
        "cron",
        hour=2,
        id="daily-weather-refresh",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        reverify_asset_hashes,
        "cron",
        day_of_week="sun",
        hour=3,
        id="weekly-asset-hash-verification",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    return scheduler
