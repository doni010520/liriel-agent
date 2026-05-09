"""
OpenAI GPT Service.

Loads Liriel's system prompt and injects:
- {contact_context} — who the person is
- {events_context} — upcoming church events
- {rag_context} — knowledge base search results
"""

from pathlib import Path

from openai import AsyncOpenAI
from loguru import logger

from app.core.config import get_settings

settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)

PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "liriel_system_prompt.txt"

_prompt_cache: str | None = None


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
