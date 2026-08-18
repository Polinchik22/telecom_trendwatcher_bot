"""
Сбор статей из RSS-источников, тегирование, перевод и дайджесты по темам.

Оптимизировано под скорость:
- скачивание RSS-лент идёт параллельно и с тайм-аутом (раньше зависание
  одного источника блокировало весь сбор без предела по времени)
- словарное тегирование ВСЕХ статей больше не запускается автоматически
  каждый день — новые статьи уже тегируются на лету при вставке; полный
  пересчёт (retag_all) остался как ручной инструмент на случай, если
  поменялся словарь tags.py
- дайджест по теме пересчитывается только если по ней вышла хотя бы
  одна новая статья с прошлого пересчёта — если тема "молчит", лишний
  запрос к LLM не делается
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor

import feedparser
import requests

from sources import SOURCES
from db import (
    insert_article,
    save_tags,
    get_all_articles_for_tagging,
    get_untagged_articles_full,
    get_untranslated_articles,
    update_article_translation,
    get_tags_needing_digest_refresh,
    get_articles_by_tag,
    save_tag_digest,
)
from tagger import tag_article, tag_text
from llm_client import llm_translate_to_english, llm_tag_article, llm_summarize_topic

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15
MAX_PARALLEL_FETCHES = 5
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TrendwatcherBot/1.0)"}


def _strip_html(text: str) -> str:
    """RSS-аннотации часто содержат HTML-разметку — убираем её для чистого текста."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fetch_feed(source: dict):
    """
    ТОЛЬКО скачивание и разбор RSS — без обращения к базе или LLM.
    Безопасно запускать параллельно для разных источников, т.к. не трогает
    ни базу данных, ни локальную модель. Всегда завершается за разумное
    время благодаря тайм-ауту (раньше именно здесь мог зависать сбор).
    """
    try:
        response = requests.get(
            source["rss_url"], timeout=REQUEST_TIMEOUT_SECONDS, headers=REQUEST_HEADERS
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        return source, feed, None
    except requests.exceptions.Timeout:
        return source, None, f"не ответил за {REQUEST_TIMEOUT_SECONDS} сек"
    except Exception as e:
        return source, None, str(e)


def _process_feed_entries(source: dict, feed) -> tuple[int, int]:
    """
    Обработка уже скачанного фида: перевод (если нужен), тегирование по
    словарю, сохранение в базу. Обращается к LLM и к базе — поэтому
    выполняется последовательно, не параллельно (локальная модель
    физически не рассчитана на несколько одновременных запросов).
    """
    found = 0
    new = 0

    for entry in feed.entries:
        found += 1

        title = entry.get("title", "Без названия")
        url = entry.get("link")
        if not url:
            continue

        published_at = entry.get("published", entry.get("updated", ""))
        summary = entry.get("summary", "")

        article_language = source["language"]
        if article_language not in ("ru", "en"):
            translated_title = llm_translate_to_english(title)
            translated_summary = llm_translate_to_english(summary)
            if translated_title is not None and translated_summary is not None:
                title = translated_title
                summary = translated_summary
                article_language = "en"
            # если перевод не удался (Ollama недоступна и т.д.) — язык
            # остаётся как есть (например "zh"), статья сохранится
            # непереведённой и попадёт в очередь на повтор при следующем
            # автосборе, вместо того чтобы навсегда "потеряться"

        article_id = insert_article(
            title=title,
            source=source["name"],
            url=url,
            published_at=published_at,
            language=article_language,
            summary=summary,
        )
        if article_id is not None:
            new += 1
            tags = tag_article(title, summary)
            save_tags(article_id, tags)

    return found, new


def collect_all() -> str:
    """
    Собирает статьи из всех источников. Скачивание RSS идёт параллельно
    (до 5 источников одновременно) с тайм-аутом на каждый — один
    зависший источник больше не может застопорить весь сбор.
    """
    lines = []
    total_new = 0

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_FETCHES) as executor:
        fetch_results = list(executor.map(_fetch_feed, SOURCES))

    for source, feed, error in fetch_results:
        if error is not None:
            lines.append(f"• {source['name']}: ❌ ошибка сети ({error})")
            continue
        if feed is None or (feed.bozo and not feed.entries):
            lines.append(f"• {source['name']}: ❌ не удалось прочитать RSS")
            continue
        try:
            found, new = _process_feed_entries(source, feed)
            total_new += new
            lines.append(f"• {source['name']}: найдено {found}, новых {new}")
        except Exception as e:
            logger.exception("Ошибка при обработке источника %s", source["name"])
            lines.append(f"• {source['name']}: ❌ ошибка обработки ({e})")

    report = "📥 Сбор завершён.\n\n" + "\n".join(lines)
    report += f"\n\nВсего новых статей: {total_new}"
    return report


def retag_all() -> str:
    """
    Прогоняет словарное тегирование по ВСЕМ статьям в базе.
    ВНИМАНИЕ: это ручной инструмент, в автоматический цикл (run_full_pipeline)
    больше не входит — новые статьи и так тегируются при сборе. Запускай
    вручную только после изменений в tags.py, чтобы применить их к уже
    собранным статьям задним числом.
    """
    articles = get_all_articles_for_tagging()
    tagged_count = 0

    for article_id, title, summary in articles:
        tags = tag_text(f"{title or ''} {summary or ''}")
        if tags:
            save_tags(article_id, tags)
            tagged_count += 1

    return (
        f"🏷 Словарное тегирование: обработано {len(articles)}, "
        f"с тегами {tagged_count}"
    )


def llm_tag_untagged(limit: int = 200) -> str:
    """LLM-тегирование статей, которые словарь не смог разметить."""
    articles = get_untagged_articles_full(limit=limit)
    if not articles:
        return "🤖 LLM-разметка: непротегированных статей не осталось."

    tagged_count = 0
    for article_id, title, summary, source in articles:
        tags = llm_tag_article(title, summary)
        if tags:
            save_tags(article_id, tags)
            tagged_count += 1

    return f"🤖 LLM-разметка: обработано {len(articles)}, размечено {tagged_count}"


def translate_existing_articles() -> str:
    """Переводит на английский статьи, у которых язык источника не 'ru' и не 'en'."""
    articles = get_untranslated_articles(limit=200)
    if not articles:
        return "🌐 Перевод: нечего переводить, всё уже на RU/EN."

    translated_count = 0
    failed_count = 0
    for article_id, title, summary in articles:
        new_title = llm_translate_to_english(title)
        new_summary = llm_translate_to_english(summary)
        if new_title is not None and new_summary is not None:
            update_article_translation(article_id, new_title, new_summary)
            translated_count += 1
        else:
            # перевод не удался — не трогаем статью, попробуем снова
            # при следующем автосборе
            failed_count += 1

    result = f"🌐 Перевод: переведено {translated_count} статей"
    if failed_count:
        result += f", не удалось {failed_count} (попробуем снова завтра)"
    return result


def compute_all_digests(articles_per_tag: int = 5) -> str:
    """
    Пересчитывает краткую выжимку "что происходит в теме" — но ТОЛЬКО для
    тегов, у которых появилась хотя бы одна новая статья с прошлого
    пересчёта. Если тема "молчит" со вчера, её дайджест не трогаем —
    экономим обращение к LLM.
    """
    tags_to_update = get_tags_needing_digest_refresh()

    if not tags_to_update:
        return "📝 Дайджесты: новых статей по темам не было, обновлять нечего."

    updated = 0
    for tag in tags_to_update:
        articles = get_articles_by_tag(tag, limit=articles_per_tag)
        if not articles:
            continue
        articles_for_llm = [
            {"title": a["title"], "summary": _strip_html(a["summary"] if "summary" in a.keys() else "")}
            for a in articles
        ]
        digest = llm_summarize_topic(tag, articles_for_llm)
        if digest:
            save_tag_digest(tag, digest)
            updated += 1

    return f"📝 Дайджесты: обновлены для {updated} из {len(tags_to_update)} тем, где были новые статьи"


def run_full_pipeline() -> str:
    """
    Автоматический цикл: сбор -> перевод оставшегося -> LLM-разметка
    непротегированного -> дайджесты по темам с новыми статьями.
    Запускается и по расписанию раз в сутки, и вручную по /collect
    (доступно только разработчику — см. bot).

    Словарное тегирование (retag_all) сюда больше не входит — оно не
    нужно каждый день, так как новые статьи тегируются на лету при сборе.
    Запускай retag_all() отдельно и вручную, только когда меняешь tags.py.
    """
    reports = [
        collect_all(),
        translate_existing_articles(),
        llm_tag_untagged(),
        compute_all_digests(),
    ]
    return "\n\n".join(reports)
