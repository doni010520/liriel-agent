"""
Webhook endpoint for receiving Uazapi messages.
"""

import asyncio

from fastapi import APIRouter, Request, Response
from loguru import logger

from app.services.uazapi import UazapiClient
from app.services.conversation import handle_incoming_message

router = APIRouter(tags=["webhook"])


@router.post("/webhook/uazapi")
async def uazapi_webhook(request: Request):
    """Receive incoming messages from Uazapi webhook.

    Responds immediately with 200 and processes in background.
    """
    try:
        payload = await request.json()
        logger.debug(f"Webhook received: {payload}")

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
