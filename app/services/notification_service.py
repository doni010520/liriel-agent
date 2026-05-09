"""
Notification Service.

Parses [NOTIFICAR:...] tags from Liriel's responses and sends
WhatsApp messages to the responsible pastor/leader.
"""

import re
from loguru import logger
from sqlalchemy import text

from app.core.database import async_session
from app.models.models import NotificationLog
from app.services.uazapi import uazapi

# ── Notification routing table ─────────────────────────────
# team_key → (description, responsible_phone)
# Phones are placeholders — replace with real numbers

NOTIFICATION_ROUTES = {
    "intercessao": ("Equipe de Intercessão", "5571999999001"),  # Pr. Diogo
    "batismo": ("Batismo", "5571999999001"),  # Pr. Diogo
    "membresia": ("Membresia", "5571999999001"),  # Pr. Diogo
    "gabinete_pastoral": ("Gabinete Pastoral", "5571999999001"),  # Pr. Diogo
    "acolhimento": ("Acolhimento", "5571999999002"),  # Pra. Tainan
    "gcs": ("Grupos de Comunhão", "5571999999003"),  # Pr. Paulo
    "beneficencia": ("Beneficência", "5571999999003"),  # Pr. Paulo
    "secretaria": ("Secretaria", "5571999999004"),  # Staff ADM
    # Ministérios por pastor
    "ministerio_adolescentes": ("Min. Adolescentes", "5571999999001"),
    "ministerio_artes": ("Min. Artes", "5571999999001"),
    "ministerio_intercessao": ("Min. Intercessão", "5571999999001"),
    "ministerio_midias": ("Min. Mídias Sociais", "5571999999001"),
    "ministerio_missoes": ("Min. Missões", "5571999999001"),
    "ministerio_acolhimento": ("Min. Acolhimento", "5571999999002"),
    "ministerio_criancas": ("Min. Crianças/Juniores", "5571999999002"),
    "ministerio_diaconato": ("Min. Diaconato", "5571999999002"),
    "ministerio_mulheres": ("Min. Mulheres", "5571999999002"),
    "ministerio_gcs": ("Min. GC's", "5571999999003"),
    "ministerio_familia": ("Min. Família", "5571999999003"),
    "ministerio_beneficencia": ("Min. Beneficência", "5571999999003"),
    "ministerio_musica": ("Min. Música", "5571999999005"),  # Pr. Saulo
    "ministerio_jovens": ("Min. Jovens", "5571999999006"),  # Pr. Silas
}

# Pattern to extract notification tags from response
NOTIFICATION_PATTERN = re.compile(
    r"\[NOTIFICAR:(\w+)\|([^|]+)\|([^\]]+)\]"
)


def extract_notifications(response_text: str) -> tuple[str, list[dict]]:
    """Extract [NOTIFICAR:...] tags from response text.

    Returns:
        Tuple of (clean_text_without_tags, list_of_notifications)
    """
    notifications = []

    for match in NOTIFICATION_PATTERN.finditer(response_text):
        notifications.append({
            "team": match.group(1).strip().lower(),
            "reason": match.group(2).strip(),
            "details": match.group(3).strip(),
        })

    # Remove tags from the text the user sees
    clean_text = NOTIFICATION_PATTERN.sub("", response_text).strip()

    return clean_text, notifications


async def process_notifications(
    notifications: list[dict],
    contact_phone: str,
    contact_name: str | None = None,
):
    """Send notifications to responsible people and log them."""
    for notif in notifications:
        team_key = notif["team"]
        reason = notif["reason"]
        details = notif["details"]

        route = NOTIFICATION_ROUTES.get(team_key)
        if not route:
            logger.warning(f"Unknown notification team: {team_key}")
            # Fallback to secretaria
            route = NOTIFICATION_ROUTES.get("secretaria", ("Secretaria", "5571999999004"))

        team_name, target_phone = route

        # Build notification message
        contact_display = contact_name or contact_phone
        message = (
            f"📋 *Notificação Liriel*\n\n"
            f"*Equipe:* {team_name}\n"
            f"*Motivo:* {reason}\n"
            f"*Contato:* {contact_display} ({contact_phone})\n"
            f"*Detalhes:* {details}"
        )

        # Send via Uazapi
        result = await uazapi.send_text(target_phone, message)

        # Log the notification
        status = "sent" if result else "failed"
        try:
            async with async_session() as db:
                log = NotificationLog(
                    team=team_key,
                    reason=reason,
                    details=details,
                    contact_phone=contact_phone,
                    contact_name=contact_name,
                    notified_phone=target_phone,
                    status=status,
                )
                db.add(log)
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to log notification: {e}")

        logger.info(
            f"Notification [{status}]: {team_name} → {target_phone} "
            f"re: {reason} ({contact_display})"
        )
