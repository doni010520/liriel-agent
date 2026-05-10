"""
Media Assets Service.

Two-stage flow for hosting binary assets in the DB and pushing them to
external services (currently the Uazapi WhatsApp profile picture):

1. Disk → DB: at boot, files in /app/assets/ are hashed and upserted into
   the media_assets table. Replacing the file + redeploying is enough to
   propagate a new asset; the hash gates the upsert so unchanged files
   are no-ops.

2. DB → Uazapi: after the sync, push_profile_picture_if_changed() compares
   the current sha256 with last_pushed_sha256 and only calls Uazapi when
   the binary actually changed. The remote side then mirrors the avatar
   to WhatsApp.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import async_session
from app.core.redis import get_redis
from app.models.models import MediaAsset
from app.services.uazapi import uazapi


_LAST_PUSHED_NAME_KEY = "liriel:profile:last_pushed_name"


# Resolve assets/ relative to the repo root (parent.parent.parent of this file)
ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"

# Map of disk filename → (db key, mime_type). Add new asset slots here.
_ASSET_FILES: dict[str, tuple[str, str]] = {
    "profile.jpg": ("profile_picture", "image/jpeg"),
}


async def sync_assets_from_disk() -> int:
    """Read assets/ from disk and upsert into media_assets.

    Returns the number of rows actually written (changed or inserted).
    Idempotent: rows whose sha256 already matches the file are skipped.
    """
    if not ASSETS_DIR.is_dir():
        logger.info(f"No assets directory at {ASSETS_DIR} — skipping sync")
        return 0

    written = 0
    async with async_session() as db:
        for filename, (key, mime_type) in _ASSET_FILES.items():
            path = ASSETS_DIR / filename
            if not path.is_file():
                logger.debug(f"Asset file missing, skipping: {path}")
                continue

            data = path.read_bytes()
            sha = hashlib.sha256(data).hexdigest()

            existing = (await db.execute(
                select(MediaAsset).where(MediaAsset.key == key)
            )).scalar_one_or_none()

            if existing is None:
                db.add(MediaAsset(
                    key=key, mime_type=mime_type, data=data, sha256=sha,
                ))
                logger.info(f"Asset inserted: {key} ({len(data)} bytes, sha256={sha[:8]}...)")
                written += 1
            elif existing.sha256 != sha:
                existing.data = data
                existing.mime_type = mime_type
                existing.sha256 = sha
                logger.info(f"Asset updated: {key} ({len(data)} bytes, sha256={sha[:8]}...)")
                written += 1
            else:
                logger.debug(f"Asset unchanged: {key} (sha256={sha[:8]}...)")

        if written:
            await db.commit()

    return written


async def push_profile_picture_if_changed() -> bool:
    """If the stored profile picture differs from what we last pushed to
    Uazapi, push it. Idempotent and safe to run on every boot.

    Returns True if a push was attempted and succeeded.
    """
    async with async_session() as db:
        asset = (await db.execute(
            select(MediaAsset).where(MediaAsset.key == "profile_picture")
        )).scalar_one_or_none()

        if asset is None:
            logger.debug("No profile_picture asset present — skipping Uazapi push")
            return False

        if asset.sha256 == asset.last_pushed_sha256:
            logger.debug(f"Profile picture already pushed (sha256={asset.sha256[:8]}...)")
            return False

        b64 = base64.b64encode(asset.data).decode("ascii")
        data_uri = f"data:{asset.mime_type};base64,{b64}"

        result = await uazapi.update_profile_image(data_uri)

        # Uazapi `_post` already returns None on non-2xx, so any dict back
        # is effectively a successful upload. The documented response shape
        # ({"success": true, ...}) doesn't actually match what the live
        # endpoint returns ({"response": "..."}), so we don't pattern-match.
        if result is None:
            logger.warning("Profile picture push to Uazapi failed (no response)")
            return False

        asset.last_pushed_sha256 = asset.sha256
        asset.last_pushed_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(
            f"Profile picture pushed to Uazapi (sha256={asset.sha256[:8]}..., "
            f"{len(asset.data)} bytes)"
        )
        return True


async def push_profile_name_if_changed() -> bool:
    """Reconcile the WhatsApp display name with settings.profile_name.

    Why we don't trust /instance/status here: Uazapi's profileName field
    in that response is the WhatsApp-side cached name and doesn't reflect
    /profile/name updates immediately (or at all in some cases). So we
    track the last-pushed value in Redis and only POST when it differs
    from the desired one — this keeps us under WhatsApp's rate limit on
    display-name changes without depending on a flaky read-back.
    """
    desired = (get_settings().profile_name or "").strip()
    if not desired:
        return False

    r = await get_redis()
    last_pushed = await r.get(_LAST_PUSHED_NAME_KEY)
    if last_pushed == desired:
        logger.debug(f"Profile name already pushed: '{desired}'")
        return False

    logger.info(f"Updating profile name: last pushed='{last_pushed}' → '{desired}'")
    result = await uazapi.update_profile_name(desired)

    if result is None:
        logger.warning("Profile name update failed (no response from Uazapi)")
        return False

    await r.set(_LAST_PUSHED_NAME_KEY, desired)
    logger.info(f"Profile name updated to '{desired}'")
    return True
