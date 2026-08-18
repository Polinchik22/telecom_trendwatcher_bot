"""
Поиск по хештегу: формирует ответ из трёх блоков (как в ТЗ, но без LLM —
резюме строится экстрактивно, из аннотации самой свежей статьи).

Поддерживает поиск по синонимам: можно написать не только канонический
тег (#5G), но и любой русский/английский синоним из таксономии
(например #пятое_поколение или #network_slicing).
"""

import html
import re

from db import get_distinct_tags, get_articles_by_tag, get_tag_dynamics, get_trending_tags, get_tag_digest, get_custom_tags
from tags import TAXONOMY
from tagger import normalize


def _strip_html(text: str) -> str:
    """RSS-аннотации часто содержат HTML-разметку — убираем её для чистого текста."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def find_matching_tag(user_input: str) -> str | None:
    """
    Ищет тег по вводу пользователя среди встроенных (tags.py) И
    пользовательских (добавленных через /addtag). Понимает:
    1. Точное совпадение с названием тега (без учёта регистра): #5g -> "5G"
    2. Совпадение с любым синонимом/ключевым словом: #network_slicing -> "NetworkSlicing"
    Тег возвращается, даже если по нему ещё нет статей (например, только
    что добавлен) — build_hashtag_report в этом случае честно скажет,
    что статей пока нет, вместо "тег не найден".
    """
    clean = normalize(user_input).lstrip("#").strip().lower().replace("_", " ")

    custom = get_custom_tags()
    all_tags = dict(TAXONOMY)
    all_tags.update(custom)

    # 1. точное совпадение с названием тега
    for tag in all_tags:
        if tag.lower() == clean:
            return tag

    # 2. совпадение с синонимом/ключевым словом (встроенным или пользовательским)
    for tag, keywords in all_tags.items():
        for kw in keywords:
            kw_clean = normalize(kw).lower().strip().rstrip("*")
            if kw_clean == clean:
                return tag

    return None


def build_hashtag_report(tag: str) -> str:
    """
    Возвращает HTML-форматированный текст (для parse_mode='HTML' в Telegram).
    Структура: краткое саммари по теме (кэшированный дайджест) + до 5
    последних статей с кликабельными ссылками + динамика упоминаемости.
    """
    articles = get_articles_by_tag(tag, limit=5)
    dynamics = get_tag_dynamics(tag)

    lines = [f"📌 <b>#{html.escape(tag)}</b>", ""]

    # --- Краткое саммари по теме (кэшируется раз в сутки вместе с автосбором) ---
    digest = get_tag_digest(tag)
    if digest:
        lines.append(html.escape(digest))
    elif articles:
        lines.append(
            f"По теме #{html.escape(tag)} за месяц вышло {dynamics['месяц']['count']} "
            "материалов. Саммари появится после следующего автообновления."
        )
    else:
        lines.append(f"По теме #{html.escape(tag)} пока нет собранных статей.")

    # --- До 5 последних статей (заголовок — кликабельная ссылка) ---
    if articles:
        lines.append("")
        lines.append("📰 <b>Свежие материалы:</b>")
        for a in articles:
            date = a["published_at"] or a["crawled_at"]
            title_escaped = html.escape(a["title"])
            url_escaped = html.escape(a["url"])
            lines.append(
                f"• <a href=\"{url_escaped}\">{title_escaped}</a>\n  {html.escape(a['source'])}, {date}"
            )

    # --- Динамика упоминаемости ---
    lines.append("")
    lines.append("📈 <b>Динамика упоминаемости:</b>")
    for label, data in dynamics.items():
        pct = data["pct_change"]
        if pct is None:
            pct_text = "нет данных за прошлый период"
        else:
            sign = "+" if pct >= 0 else ""
            pct_text = f"{sign}{pct}% к предыдущему периоду"
        lines.append(f"  {label}: {data['count']} статей ({pct_text})")

    return "\n".join(lines)


def build_actual_report() -> str:
    """
    Функция «Актуальные»: топ-3 темы с наибольшим приростом упоминаний
    за неделю, по одной самой свежей статье на каждую. Если у бота ещё
    мало истории для честного сравнения периодов — показывает просто
    самые обсуждаемые темы за неделю, без ярлыка "прирост".
    """
    trending = get_trending_tags(limit=3, period_days=7)

    if not trending:
        return (
            "Пока недостаточно данных, чтобы определить актуальные темы.\n"
            "Собери больше статей (/collect) и попробуй ещё раз чуть позже."
        )

    insufficient_history = trending[0].get("insufficient_history", False)
    title = (
        "📊 <b>3 самые обсуждаемые темы за неделю</b>\n"
        "<i>(бот собирает статьи меньше 2 недель — для честного расчёта прироста нужно больше истории)</i>"
        if insufficient_history
        else "🔥 <b>3 актуальные темы прямо сейчас</b>"
    )
    lines = [title, ""]

    for i, t in enumerate(trending, 1):
        articles = get_articles_by_tag(t["tag"], limit=1)
        if not articles:
            continue
        a = articles[0]
        annotation = _strip_html(a["summary"] if "summary" in a.keys() else "")
        trimmed = annotation[:300] + ("…" if len(annotation) > 300 else "")

        if t.get("insufficient_history"):
            growth_text = f"{t['current']} статей за неделю"
        elif t["pct"] is None:
            growth_text = "новая тема — раньше не встречалась"
        else:
            sign = "+" if t["pct"] >= 0 else ""
            growth_text = f"{sign}{t['pct']}% за неделю"

        lines.append(f"{i}. <b>#{html.escape(t['tag'])}</b> ({growth_text})")
        lines.append(f"<a href=\"{html.escape(a['url'])}\">{html.escape(a['title'])}</a>")
        lines.append(html.escape(a["source"]))
        if trimmed:
            lines.append(f"<i>{html.escape(trimmed)}</i>")
        lines.append("")

    return "\n".join(lines).strip()
