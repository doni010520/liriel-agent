"""
OpenAI GPT Service.

Loads Liriel's system prompt and injects:
- {current_datetime} — Salvador/BA local time, so the model greets correctly
- {contact_context} — who the person is
- {events_context} — upcoming church events
- {rag_context} — knowledge base search results
"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from loguru import logger

from app.core.config import get_settings

settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "liriel_system_prompt.txt"

_prompt_cache: str | None = None

SALVADOR_TZ = ZoneInfo("America/Bahia")
_WEEKDAYS_PT = [
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
]


def _current_datetime_pt() -> str:
    """Format Salvador/BA local time as a Portuguese phrase the model can read.

    Example: "domingo, 10/05/2026, 08:14 (manhã)"
    """
    now = datetime.now(SALVADOR_TZ)
    weekday = _WEEKDAYS_PT[now.weekday()]
    hour = now.hour
    if hour < 5:
        period = "madrugada"
    elif hour < 12:
        period = "manhã"
    elif hour < 18:
        period = "tarde"
    else:
        period = "noite"
    return f"{weekday}, {now.strftime('%d/%m/%Y')}, {now.strftime('%H:%M')} ({period})"


def _load_prompt() -> str:
    global _prompt_cache
    if _prompt_cache is None:
        if PROMPT_PATH.exists():
            _prompt_cache = PROMPT_PATH.read_text(encoding="utf-8")
            logger.info(f"System prompt loaded ({len(_prompt_cache)} chars)")
        else:
            logger.warning(f"Prompt file not found: {PROMPT_PATH}")
            _prompt_cache = (
                "Você é Liriel, assistente virtual da Igreja Batista Lírio dos Vales "
                "de Jardim Armação, em Salvador/BA. Responda com acolhimento e amor."
            )
    return _prompt_cache


def build_system_prompt(
    contact_context: str = "",
    events_context: str = "",
    rag_context: str = "",
) -> str:
    """Build the full system prompt with all dynamic contexts injected."""
    template = _load_prompt()
    return (
        template
        .replace("{current_datetime}", _current_datetime_pt())
        .replace("{contact_context}", contact_context or "Primeiro contato — informações ainda não disponíveis.")
        .replace("{events_context}", events_context or "Nenhum evento cadastrado no momento.")
        .replace("{rag_context}", rag_context or "")
    )


async def generate_response(
    messages_history: list[dict],
    user_message: str,
    contact_context: str = "",
    events_context: str = "",
    rag_context: str = "",
) -> tuple[str, int]:
    """Generate GPT response with all contexts.

    Returns (response_text, total_tokens_used).
    Response may contain [NOTIFICAR:...] tags to be processed by notification_service.
    """
    prompt = build_system_prompt(contact_context, events_context, rag_context)

    messages = [{"role": "system", "content": prompt}]
    messages.extend(messages_history)
    messages.append({"role": "user", "content": user_message})

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=settings.openai_temperature,
            max_tokens=settings.openai_max_tokens,
        )

        reply = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0

        logger.info(f"GPT response ({tokens} tokens)")
        return reply.strip(), tokens

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return (
            "Desculpe, tive um probleminha aqui 😊 Pode tentar de novo?",
            0,
        )


SUMMARY_PROMPT = """Você está sumarizando uma conversa do WhatsApp entre Liriel \
(assistente da Igreja Batista Lírio dos Vales de Jardim Armação) e uma pessoa \
da igreja, para que a Liriel mantenha contexto em conversas longas.

Resuma em 4-8 frases curtas, em português, capturando:
- Nome da pessoa e vínculo (membro/congregado/visitante), se mencionados
- Dados pessoais coletados (aniversário, bairro, como conheceu)
- Pedidos ou interesses (oração, batismo, GC, ministério, eventos)
- Situações delicadas, pendências, ou pedidos não resolvidos
- Tom geral e qualquer informação importante para continuar a conversa

Não invente informação que não esteja no histórico. Se não houver dados pessoais, \
foque nos pedidos e tom da conversa. Não cite a Liriel em terceira pessoa — \
escreva como notas operacionais ("Pessoa pediu oração... informou que mora em ...").

Conversa:
---
{history}
---

Resumo operacional:"""


async def summarize_conversation(history_text: str) -> str | None:
    """Generate a rolling summary of older conversation messages."""
    if not history_text.strip():
        return None
    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": SUMMARY_PROMPT.format(history=history_text)}],
            temperature=0.2,
            max_tokens=400,
        )
        summary = (response.choices[0].message.content or "").strip()
        return summary or None
    except Exception as e:
        logger.error(f"Summary generation error: {e}")
        return None
