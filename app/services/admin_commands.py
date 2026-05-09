"""
Admin Command Parser.

Parses admin commands from WhatsApp messages for event management.
"""

import re
from datetime import datetime, date
from loguru import logger
from app.services.events_service import add_event, remove_event, list_future_events


async def parse_admin_command(message: str, admin_phone: str) -> str | None:
    """Parse and execute admin commands.

    Returns response text if it was a command, None if not a command.
    """
    msg = message.strip()

    # Check if it starts with "Liriel," (case-insensitive)
    if not re.match(r"(?i)^liriel\s*,", msg):
        return None

    # Remove the "Liriel," prefix
    command_text = re.sub(r"(?i)^liriel\s*,\s*", "", msg).strip()

    # ── Add event ──
    add_match = re.match(r"(?i)adicionar evento\s*:\s*(.+)", command_text)
    if add_match:
        return await _handle_add_event(add_match.group(1).strip(), admin_phone)

    # ── Remove event ──
    remove_match = re.match(r"(?i)remover evento\s*:\s*(.+)", command_text)
    if remove_match:
        return await _handle_remove_event(remove_match.group(1).strip())

    # ── List events ──
    if re.match(r"(?i)listar eventos", command_text):
        return await _handle_list_events()

    return None


async def _handle_add_event(raw: str, admin_phone: str) -> str:
    """Parse: Nome, DD/MM/YYYY, HHh às HHh, Local, Descrição"""
    parts = [p.strip() for p in raw.split(",")]

    if len(parts) < 2:
        return (
            "Formato: Liriel, adicionar evento: Nome, DD/MM/YYYY, "
            "HHh às HHh, Local, Descrição"
        )

    name = parts[0]

    # Parse date
    event_date = _parse_date(parts[1])
    if not event_date:
        return f"Data inválida: '{parts[1]}'. Use o formato DD/MM/YYYY."

    # Parse times (optional)
    start_time = ""
    end_time = ""
    if len(parts) >= 3:
        time_str = parts[2]
        time_parts = re.split(r"\s+(?:às|a|até|-)\s+", time_str, maxsplit=1)
        start_time = time_parts[0].strip()
        if len(time_parts) > 1:
            end_time = time_parts[1].strip()

    # Location (optional)
    location = parts[3] if len(parts) >= 4 else ""

    # Description (optional, everything after location)
    description = ", ".join(parts[4:]) if len(parts) >= 5 else ""

    result = await add_event(
        name=name,
        event_date=event_date,
        start_time=start_time,
        end_time=end_time,
        location=location,
        description=description,
        created_by=admin_phone,
    )

    if result:
        time_display = start_time
        if end_time:
            time_display += f" às {end_time}"

        response = f"Evento cadastrado com sucesso! ✅\n\n*{name}*\n📅 {parts[1]}"
        if time_display:
            response += f", {time_display}"
        if location:
            response += f"\n📍 {location}"
        if description:
            response += f"\n📝 {description}"
        return response
    else:
        return "Ocorreu um erro ao cadastrar o evento. Tente novamente."


async def _handle_remove_event(name: str) -> str:
    """Remove event by name."""
    success = await remove_event(name)
    if success:
        return f"Evento *{name}* removido com sucesso! ✅"
    else:
        return f"Evento '{name}' não encontrado nos eventos futuros."


async def _handle_list_events() -> str:
    """List all future events."""
    events = await list_future_events(days_ahead=180)
    if not events:
        return "Nenhum evento futuro cadastrado no momento."

    lines = ["📅 *Eventos futuros:*\n"]
    for e in events:
        line = f"• *{e['name']}* — {e['date']}"
        if e["start_time"]:
            line += f", {e['start_time']}"
            if e["end_time"]:
                line += f" às {e['end_time']}"
        if e["location"]:
            line += f" — {e['location']}"
        lines.append(line)

    return "\n".join(lines)


def _parse_date(text: str) -> date | None:
    """Parse various date formats."""
    text = text.strip()
    formats = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    return None
