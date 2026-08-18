"""
Клиент для облачной LLM через Groq (вместо локальной Ollama — нужно для
переноса бота на сервер без видеокарты).

Groq API OpenAI-совместимый, поэтому используется официальная библиотека
groq. Бесплатный тариф Groq: ~1000 запросов в день, без привязки карты —
для личного бота с нашей нагрузкой должно хватать с запасом.

Все функции безопасны: при любой ошибке (нет ключа, сеть недоступна,
превышен лимит и т.д.) они не роняют бота, а просто возвращают "ничего
не нашлось" — тогда бот скажет пользователю, что не разобралась.
"""

import json
import logging
import time

from groq import Groq

from tags import TAXONOMY
from db import get_custom_tags

logger = logging.getLogger(__name__)

# ==== ВСТАВЬ СВОЙ КЛЮЧ ОТ GROQ СЮДА (между кавычками) ====
GROQ_API_KEY = "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"
# ============================================================

# Groq периодически меняет набор доступных моделей — если эта тоже
# перестанет работать, актуальный список смотри на console.groq.com/docs/models
# или запросом к https://api.groq.com/openai/v1/models
MODEL_NAME = "openai/gpt-oss-20b"

# Небольшая пауза после каждого запроса — на бесплатном тарифе Groq лимит
# ~30 запросов в минуту. Если долбить без пауз (например, при переводе
# сразу многих статей подряд), можно упереться в лимит. 2 секунды между
# запросами держат нас заметно ниже потолка.
RATE_LIMIT_DELAY_SECONDS = 2

_client = Groq(api_key=GROQ_API_KEY)


def _all_known_tags() -> list[str]:
    """Встроенные теги + пользовательские, добавленные через бота — всегда актуально."""
    return list(TAXONOMY.keys()) + list(get_custom_tags().keys())


def _groq_chat(prompt: str, json_mode: bool = False, temperature: float = 0) -> str | None:
    """
    Общая обёртка над вызовом Groq — один запрос, с паузой после для
    защиты от лимита запросов в минуту. Возвращает текст ответа модели
    или None при любой ошибке.
    """
    if GROQ_API_KEY == "ВСТАВЬ_СЮДА_КЛЮЧ_ОТ_GROQ":
        logger.warning("GROQ_API_KEY не задан — LLM-функции не будут работать.")
        return None

    kwargs = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = _client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        time.sleep(RATE_LIMIT_DELAY_SECONDS)
        return content
    except Exception as e:
        logger.warning("Ошибка запроса к Groq: %s", e)
        time.sleep(RATE_LIMIT_DELAY_SECONDS)
        return None


def llm_tag_article(title: str, summary: str) -> list[str]:
    """Просит модель выбрать подходящие теги из фиксированного списка для статьи."""
    all_tags = _all_known_tags()
    tags_list_text = ", ".join(all_tags)

    prompt = (
        "Ты — классификатор новостей телеком-отрасли.\n"
        f"Заголовок: {title}\n"
        f"Аннотация: {summary}\n\n"
        f"Список допустимых тегов: {tags_list_text}\n\n"
        "Отметь ВСЕ теги из этого списка, которые подходят по смыслу — "
        "статья часто относится сразу к нескольким темам одновременно. "
        "Не придумывай теги, которых нет в списке. Ответь строго JSON "
        'вида {"tags": ["5G", "Operators"]}, без пояснений.'
    )

    content = _groq_chat(prompt, json_mode=True, temperature=0)
    if content is None:
        return []

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            list_values = [v for v in parsed.values() if isinstance(v, list)]
            parsed = list_values[0] if list_values else []
        if not isinstance(parsed, list):
            return []
        result = [t for t in parsed if isinstance(t, str) and t in all_tags]
        if not result:
            logger.info("LLM не нашла подходящих тегов для статьи '%s' (ответ: %r)", title, content)
        return result
    except Exception as e:
        logger.warning("Ошибка разбора ответа LLM-тегирования: %s (ответ: %r)", e, content)
        return []


def llm_match_query(query_text: str) -> str | None:
    """Определяет, к какому ОДНОМУ тегу из списка ближе всего запрос пользователя."""
    all_tags = _all_known_tags()
    tags_list_text = ", ".join(all_tags)

    prompt = (
        "Пользователь ищет новости на определённую тему.\n"
        f"Список тегов: {tags_list_text}\n\n"
        f'Запрос пользователя: "{query_text}"\n\n'
        "Определи ОДИН тег из списка, который ближе всего подходит по "
        "смыслу. Если ни один тег не подходит — ответь ровно словом: none. "
        "Ответь ТОЛЬКО названием тега из списка (точно как в списке) или "
        "словом none, без пояснений и знаков препинания."
    )

    content = _groq_chat(prompt, json_mode=False, temperature=0)
    if content is None:
        return None

    content = content.strip()
    for tag in all_tags:
        if tag.lower() == content.lower():
            return tag
    return None


def llm_translate_to_english(text: str) -> str | None:
    """
    Переводит текст на английский. Возвращает None при ЛЮБОЙ ошибке —
    вызывающий код не должен путать неудачу с успешным переводом (иначе
    статья навсегда останется непереведённой под видом "en").
    """
    if not text or not text.strip():
        return text

    prompt = (
        "Translate the following text to English. "
        "Respond with ONLY the translation, no explanations, no quotes:\n\n"
        f"{text}"
    )

    content = _groq_chat(prompt, json_mode=False, temperature=0)
    if content is None:
        return None
    translated = content.strip()
    return translated if translated else None


def llm_summarize_topic(tag: str, articles: list[dict]) -> str:
    """Строит краткую выжимку "что сейчас происходит в этой сфере" по последним статьям темы."""
    if not articles:
        return ""

    articles_text = "\n\n".join(
        f"- {a['title']}: {a['summary'][:300]}" for a in articles if a.get("title")
    )
    if not articles_text:
        return ""

    prompt = (
        f"Вот последние новости по теме «{tag}» в телеком-отрасли:\n\n"
        f"{articles_text}\n\n"
        "Напиши краткую выжимку (3-5 предложений) на русском языке: что "
        "сейчас происходит в этой сфере, судя по этим новостям, какая "
        "общая картина. Пиши связным текстом, без списка и без вступлений "
        'вроде "Вот выжимка".'
    )

    content = _groq_chat(prompt, json_mode=False, temperature=0.3)
    return content.strip() if content else ""


def llm_generate_keywords(tag_name: str) -> list[str]:
    """Придумывает ключевые слова (RU+EN) для нового пользовательского тега."""
    prompt = (
        f'Придумай ключевые слова и синонимы (на русском И английском) для '
        f'поиска статей по теме "{tag_name}" в новостях телеком-отрасли. '
        "Нужно 4-8 вариантов: сокращения, устойчивые формулировки, "
        "англоязычные термины, которые реально встречаются в новостях. "
        'Ответь строго JSON вида {"keywords": ["blockchain", "блокчейн"]}, без пояснений.'
    )

    content = _groq_chat(prompt, json_mode=True, temperature=0.3)
    if content is None:
        return []

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            list_values = [v for v in parsed.values() if isinstance(v, list)]
            parsed = list_values[0] if list_values else []
        if not isinstance(parsed, list):
            return []
        return [k.strip() for k in parsed if isinstance(k, str) and k.strip()]
    except Exception as e:
        logger.warning("Ошибка разбора ключевых слов для тега %s: %s (ответ: %r)", tag_name, e, content)
        return []
