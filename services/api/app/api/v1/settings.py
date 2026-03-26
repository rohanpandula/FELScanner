"""
Settings API Endpoints
Application configuration management
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings as get_app_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.settings import Setting
from app.schemas.settings import (
    BackgroundTaskSettings,
    CollectionSettings,
    NotificationSettings,
    SettingCreate,
    SettingResponse,
    SettingUpdate,
)

router = APIRouter()
logger = get_logger(__name__)


@router.get("", response_model=list[SettingResponse])
@router.get("/", response_model=list[SettingResponse], include_in_schema=False)
async def list_settings(
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    List all settings

    Returns all application settings from the database.
    Optionally filter by category.
    """
    query = select(Setting)

    if category:
        query = query.where(Setting.category == category)

    result = await db.execute(query.order_by(Setting.key))
    settings = result.scalars().all()

    return settings


@router.get("/{key}", response_model=SettingResponse)
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get a specific setting by key

    Returns the setting value and metadata.
    """
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()

    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")

    return setting


@router.post("", response_model=SettingResponse, status_code=201)
@router.post("/", response_model=SettingResponse, status_code=201, include_in_schema=False)
async def create_setting(
    setting_create: SettingCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new setting

    Creates a new configuration key-value pair.
    """
    # Check if key already exists
    result = await db.execute(
        select(Setting).where(Setting.key == setting_create.key)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail="Setting key already exists")

    setting = Setting(**setting_create.model_dump())
    db.add(setting)
    await db.commit()
    await db.refresh(setting)

    logger.info("setting.created", key=setting.key, category=setting.category)

    return setting


@router.patch("/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    setting_update: SettingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update a setting

    Updates the value and metadata of an existing setting.
    """
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()

    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")

    # Update fields
    update_data = setting_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(setting, field, value)

    # Increment version
    setting.version += 1

    await db.commit()
    await db.refresh(setting)

    logger.info(
        "setting.updated",
        key=setting.key,
        version=setting.version,
        updated_by=setting_update.updated_by,
    )

    return setting


@router.delete("/{key}", status_code=204)
async def delete_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a setting

    Removes a configuration key-value pair.
    """
    result = await db.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()

    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")

    await db.delete(setting)
    await db.commit()

    logger.info("setting.deleted", key=key)


@router.get("/notifications/config", response_model=NotificationSettings)
async def get_notification_settings():
    """
    Get notification configuration

    Returns all 17 notification rules from environment config.
    """
    config = get_app_settings()
    return NotificationSettings(**config.notification_config)


@router.get("/collections/config", response_model=CollectionSettings)
async def get_collection_settings():
    """
    Get collection configuration

    Returns Plex collection settings.
    """
    config = get_app_settings()

    return CollectionSettings(
        collection_name_all_dv=config.COLLECTION_NAME_ALL_DV,
        collection_name_profile7=config.COLLECTION_NAME_PROFILE7,
        collection_name_truehd_atmos=config.COLLECTION_NAME_TRUEHD_ATMOS,
        collection_enable_dv=config.COLLECTION_ENABLE_DV,
        collection_enable_p7=config.COLLECTION_ENABLE_P7,
        collection_enable_atmos=config.COLLECTION_ENABLE_ATMOS,
    )


@router.get("/tasks/config", response_model=BackgroundTaskSettings)
async def get_background_task_settings():
    """
    Get background task configuration

    Returns scheduling and auto-start settings.
    """
    config = get_app_settings()

    return BackgroundTaskSettings(
        scan_frequency_hours=config.SCAN_FREQUENCY_HOURS,
        monitor_interval_minutes=config.MONITOR_INTERVAL_MINUTES,
        connection_check_interval_minutes=config.CONNECTION_CHECK_INTERVAL_MINUTES,
        auto_start_mode=config.AUTO_START_MODE,
    )
