"""
Webhook endpoint for receiving Uazapi messages.
"""

import asyncio
import json

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.redis import get_redis
from app.services.uazapi import UazapiClient
from app.services.conversation import handle_incoming_message

router = APIRouter(tags=["webhook"])

_LAST_PAYLOAD_KEY = "liriel:diag:last_webhook_payload"


@router.post("/webhook/uazapi")
async def uazapi_webhook(request: Request):
    """Receive incoming messages from Uazapi webhook.

    Responds immediately with 200 and processes in background.
    """
    try:
        payload = await request.json()
        logger.info(f"Webhook payload: {payload}")

        # Save raw payload for diagnostics (TTL 1h)
        try:
            r = await get_redis()
            await r.set(_LAST_PAYLOAD_KEY, json.dumps(payload, ensure_ascii=False), ex=3600)
        except Exception:
            pass

        # Parse the webhook payload
        parsed = UazapiClient.parse_webhook(payload)

        if parsed is None:
            # Not a processable message (status update, group, etc.)
            return Response(status_code=200)

        # Process in background (don't block webhook response)
        asyncio.create_task(handle_incoming_message(parsed))

        return Response(status_code=200)

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        # Always return 200 to prevent Uazapi from retrying
        return Response(status_code=200)


@router.get("/webhook/last")
async def last_webhook_payload():
    """Return the last raw webhook payload received (diagnostic only)."""
    try:
        r = await get_redis()
        raw = await r.get(_LAST_PAYLOAD_KEY)
        if raw is None:
            return JSONResponse({"error": "no payload captured yet"}, status_code=404)
        return JSONResponse(json.loads(raw))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
