"""
Contact Updater Service.

Parses [CADASTRO:...] tags from Liriel's responses and updates
the contact record in the database.
"""

import re
from datetime import datetime, date

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Contact

# Pattern to extract cadastro tags
CADASTRO_PATTERN = re.compile(r"\[CADASTRO:([^\]]+)\]")


def extract_cadastro(response_text: str) -> tuple[str, dict]:
    """Extract [CADASTRO:...] tags from response text.

    Returns:
        Tuple of (clean_text_without_tags, dict_of_fields)
    """
    fields = {}

    for match in CADASTRO_PATTERN.finditer(response_text):
        raw = match.group(1)
        for pair in raw.split("|"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                fields[key.strip().lower()] = value.strip()

    clean_text = CADASTRO_PATTERN.sub("", response_text).strip()
    return clean_text, fields


async def update_contact_from_cadastro(
    db: AsyncSession, phone: str, fields: dict
) -> bool:
    """Update contact record with extracted fields.

    Accepted fields: nome, status, aniversario, bairro, como_conheceu
    """
    if not fields:
        return False

    try:
        result = await db.execute(select(Contact).where(Contact.phone == phone))
        contact = result.scalar_one_or_none()

        if not contact:
            logger.warning(f"Contact not found for update: {phone}")
            return False

        updated = False

        if "nome" in fields and fields["nome"]:
            contact.name = fields["nome"]
            updated = True

        if "status" in fields and fields["status"]:
            status = _normalize_status(fields["status"])
            if status:
                contact.status = status
                updated = True

        if "aniversario" in fields and fields["aniversario"]:
            birthday = _parse_birthday(fields["aniversario"])
            if birthday:
                contact.birthday = birthday
                updated = True

        if "bairro" in fields and fields["bairro"]:
            contact.neighborhood = fields["bairro"]
            updated = True

        if "como_conheceu" in fields and fields["como_conheceu"]:
            contact.how_found = fields["como_conheceu"]
            updated = True

        if updated:
            await db.commit()
            logger.info(
                f"Contact updated [{phone}]: "
                + ", ".join(f"{k}={v}" for k, v in fields.items())
            )

        return updated

    except Exception as e:
        logger.error(f"Error updating contact: {e}")
        return False


def _normalize_status(raw: str) -> str | None:
    """Normalize status to one of: membro, congregado, visitante."""
    raw_lower = raw.lower().strip()
    if "membro" in raw_lower:
        return "membro"
    if "congregad" in raw_lower:
        return "congregado"
    if "visitante" in raw_lower or "visit" in raw_lower:
        return "visitante"
    return None


def _parse_birthday(raw: str) -> date | None:
    """Parse birthday from various formats."""
    raw = raw.strip()

    # Try DD/MM/YYYY
    formats = ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"]
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    # Try DD/MM (use year 2000 as placeholder)
    try:
        parsed = datetime.strptime(raw, "%d/%m")
        return parsed.replace(year=2000).date()
    except ValueError:
        pass

    # Try "15 de março" style
    months = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
        "abril": 4, "maio": 5, "junho": 6, "julho": 7,
        "agosto": 8, "setembro": 9, "outubro": 10,
        "novembro": 11, "dezembro": 12,
    }

    raw_lower = raw.lower()
    for month_name, month_num in months.items():
        if month_name in raw_lower:
            # Extract day number
            day_match = re.search(r"(\d{1,2})", raw)
            if day_match:
                day = int(day_match.group(1))
                # Check for year
                year_match = re.search(r"(\d{4})", raw)
                year = int(year_match.group(1)) if year_match else 2000
                try:
                    return date(year, month_num, day)
                except ValueError:
                    pass
            break

    logger.warning(f"Could not parse birthday: {raw}")
    return None
