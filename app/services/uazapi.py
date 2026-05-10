"""
Uazapi v2 WhatsApp API Client.

Endpoints from OpenAPI spec v2.1.0:
- POST /send/text       → Send text message
- POST /send/media      → Send media (image, video, audio, document, ptt, sticker)
- POST /message/download → Download media + optional audio transcription
- Auth: header "token"
"""

import httpx
from loguru import logger
from app.core.config import get_settings

settings = get_settings()


class UazapiClient:
    """Client for Uazapi v2.1 WhatsApp API."""

    def __init__(self):
        self.base_url = settings.uazapi_base_url.rstrip("/")
        self.token = settings.uazapi_api_key
        self.timeout = httpx.Timeout(60.0)

    @property
    def headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "token": self.token,
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    # ── Send Messages ──────────────────────────────────────────

    async def send_text(
        self,
        phone: str,
        text: str,
        delay: int = 0,
        reply_id: str | None = None,
    ) -> dict | None:
        """POST /send/text"""
        payload: dict = {"number": phone, "text": text}
        if delay:
            payload["delay"] = delay
        if reply_id:
            payload["replyid"] = reply_id

        return await self._post("/send/text", payload)

    async def send_media(
        self,
        phone: str,
        media_type: str,
        file: str,
        caption: str = "",
        doc_name: str = "",
    ) -> dict | None:
        """POST /send/media

        Args:
            media_type: image | video | document | audio | ptt | sticker
            file: URL or base64 string
        """
        payload: dict = {
            "number": phone,
            "type": media_type,
            "file": file,
        }
        if caption:
            payload["text"] = caption
        if doc_name:
            payload["docName"] = doc_name

        return await self._post("/send/media", payload)

    # ── Download / Transcribe ──────────────────────────────────

    async def download_media(
        self,
        message_id: str,
        return_base64: bool = False,
        return_link: bool = True,
        transcribe: bool = False,
        generate_mp3: bool = True,
    ) -> dict | None:
        """POST /message/download

        Returns: { fileURL, mimetype, base64Data, transcription }
        """
        payload: dict = {
            "id": message_id,
            "return_base64": return_base64,
            "return_link": return_link,
            "transcribe": transcribe,
            "generate_mp3": generate_mp3,
        }
        return await self._post("/message/download", payload)

    async def transcribe_audio(self, message_id: str) -> str | None:
        """Download and transcribe audio message.
        Uses Uazapi's built-in Whisper transcription.

        Returns transcribed text or None.
        """
        result = await self.download_media(
            message_id=message_id,
            transcribe=True,
            return_link=False,
            return_base64=False,
        )
        if result and result.get("transcription"):
            return result["transcription"]
        return None

    async def get_media_base64(self, message_id: str) -> tuple[str, str] | None:
        """Download media as base64.

        Returns (base64_data, mimetype) or None.
        """
        result = await self.download_media(
            message_id=message_id,
            return_base64=True,
            return_link=False,
        )
        if result and result.get("base64Data"):
            return result["base64Data"], result.get("mimetype", "")
        return None

    async def get_media_url(self, message_id: str) -> str | None:
        """Download media and get public URL.

        Returns URL string or None.
        """
        result = await self.download_media(
            message_id=message_id,
            return_base64=False,
            return_link=True,
        )
        if result and result.get("fileURL"):
            return result["fileURL"]
        return None

    async def download_quoted_media(
        self,
        message_id: str,
        return_base64: bool = True,
    ) -> dict | None:
        """Download media from a quoted/replied message.

        Uses download_quoted=true to get the original media
        when user replies to a status/image/document.

        Returns: { fileURL, mimetype, base64Data }
        """
        payload: dict = {
            "id": message_id,
            "download_quoted": True,
            "return_base64": return_base64,
            "return_link": not return_base64,
        }
        return await self._post("/message/download", payload)

    # ── Internal ───────────────────────────────────────────────

    async def _post(self, path: str, payload: dict) -> dict | None:
        url = self._url(path)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url, json=payload, headers=self.headers
                )
                response.raise_for_status()
                result = response.json()
                logger.debug(f"Uazapi {path} → {response.status_code}")
                return result
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Uazapi {path} HTTP {e.response.status_code}: "
                f"{e.response.text[:300]}"
            )
            return None
        except Exception as e:
            logger.error(f"Uazapi {path} error: {e}")
            return None

    # ── Webhook Parser ─────────────────────────────────────────

    @staticmethod
    def parse_webhook(payload: dict) -> dict | None:
        """Parse incoming Uazapi v2 webhook into normalized format.

        Actual Uazapi v2 payload structure:
        {
            "EventType": "messages",
            "message": {
                "chatid": "557193061031@s.whatsapp.net",
                "sender_pn": "557193061031@s.whatsapp.net",
                "senderName": "Adonias Santos",
                "text": "Hello",
                "messageid": "3EB01963E905F31A3D658A",
                "isGroup": false,
                "fromMe": false,
                "messageType": "Conversation",
                "quoted": "",
                "content": "...",
                ...
            },
            "chat": { "phone": "+55 71 9306-1031", ... },
            ...
        }
        """
        try:
            event = payload.get("event") or payload.get("EventType", "")

            # Only process incoming messages
            if event not in ("message", "messages"):
                logger.debug(f"Ignoring webhook event: {event}")
                return None

            # Message data is in payload["message"], not payload["data"]
            msg = payload.get("message") or payload.get("data", {})

            # Skip messages sent by us
            if msg.get("fromMe", False):
                return None

            # Skip group messages
            if msg.get("isGroup", False):
                return None

            # Extract phone from chatid or sender_pn
            chat_id = (
                msg.get("chatid")
                or msg.get("sender_pn")
                or msg.get("sender", "")
            )
            phone = chat_id.split("@")[0] if chat_id else ""

            # If phone is a LID (not digits), try sender_pn
            if not phone or not phone.isdigit():
                sender_pn = msg.get("sender_pn", "")
                phone = sender_pn.split("@")[0] if sender_pn else ""

            # Last resort: try chat.phone field
            if not phone or not phone.isdigit():
                chat_data = payload.get("chat", {})
                raw_phone = chat_data.get("phone", "")
                # Clean "+55 71 9306-1031" → "557193061031"
                phone = "".join(c for c in raw_phone if c.isdigit())

            if not phone or not phone.isdigit():
                logger.warning(f"Invalid phone from webhook: {chat_id}")
                return None

            # Message type mapping
            msg_type_raw = msg.get("messageType") or msg.get("type", "conversation")
            msg_type = _normalize_message_type(msg_type_raw)

            # Message ID for media download
            message_id = msg.get("messageid") or msg.get("id", "")

            # Text content
            text = msg.get("text", "")

            return {
                "phone": phone,
                "body": str(text).strip() if text else "",
                "type": msg_type,
                "type_raw": msg_type_raw,
                "push_name": msg.get("senderName", ""),
                "message_id": message_id,
                "quoted_id": msg.get("quoted", ""),
                "timestamp": msg.get("messageTimestamp", 0),
                "content": msg.get("content", {}),
            }

        except Exception as e:
            logger.error(f"Error parsing webhook: {e}")
            return None


def _normalize_message_type(raw_type: str) -> str:
    """Map Uazapi messageType to our internal types."""
    mapping = {
        "conversation": "text",
        "Conversation": "text",
        "extendedTextMessage": "text",
        "imageMessage": "image",
        "videoMessage": "video",
        "audioMessage": "audio",
        "pttMessage": "audio",
        "documentMessage": "document",
        "documentWithCaptionMessage": "document",
        "stickerMessage": "sticker",
        "contactMessage": "contact",
        "locationMessage": "location",
        "reactionMessage": "reaction",
        "pollCreationMessage": "poll",
        "PollUpdateMessage": "poll_update",
        "viewOnceMessageV2": "view_once",
    }
    return mapping.get(raw_type, raw_type)


# Singleton
uazapi = UazapiClient()
