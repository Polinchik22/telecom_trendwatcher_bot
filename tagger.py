"""
Тегирование статей: сопоставляем текст статьи (заголовок + аннотация)
с таксономией хештегов.

Используется сопоставление по ГРАНИЦАМ слов (а не любая подстрока) —
так "ии" не сработает внутри слова "заявили", а "5g" не сработает
внутри произвольного набора символов.

Также текст нормализуется перед сравнением: разные "похожие на дефис"
юникод-символы (‑ – —) приводятся к обычному дефису, неразрывные
пробелы — к обычным. Без этого, например, "Wi‑Fi" (с типографским
дефисом) не совпадало бы с ключевым словом "wi-fi".
"""

import re

from tags import TAXONOMY
from db import get_custom_tags

_DASH_CHARS = ["\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015"]


def normalize(text: str) -> str:
    for dash in _DASH_CHARS:
        text = text.replace(dash, "-")
    text = text.replace("\xa0", " ")
    return text


def _keyword_pattern(keyword: str) -> re.Pattern:
    """
    Строит регулярку с границей слова СЛЕВА всегда, а справа — только если
    ключевое слово не помечено как "корень" через *.
    Например "коаксиал*" совпадёт и с "коаксиальный", и с "коаксиальном",
    а "5g" (без *) совпадёт только с отдельным словом "5g", не с "5gb".
    """
    is_stem = keyword.endswith("*")
    raw = keyword[:-1] if is_stem else keyword
    escaped = re.escape(normalize(raw).lower().strip())

    if is_stem:
        return re.compile(r"(?<![a-zа-яё0-9])" + escaped)
    return re.compile(r"(?<![a-zа-яё0-9])" + escaped + r"(?![a-zа-яё0-9])")


# Предкомпилируем паттерны встроенного словаря один раз при импорте —
# он статичный (меняется только руками в tags.py). Пользовательские теги
# добавляются людьми через бота в любой момент, поэтому их подгружаем
# из базы заново при каждом вызове tag_text — стоит недорого на масштабе
# прототипа, а места для рассинхронизации не остаётся.
_COMPILED_TAXONOMY = {
    tag: [_keyword_pattern(kw) for kw in keywords]
    for tag, keywords in TAXONOMY.items()
}


def tag_text(text: str) -> list[str]:
    """Возвращает список тегов (без символа #), подходящих для данного текста."""
    if not text:
        return []

    text_norm = normalize(text).lower()
    matched = []

    for tag, patterns in _COMPILED_TAXONOMY.items():
        for pattern in patterns:
            if pattern.search(text_norm):
                matched.append(tag)
                break

    for tag, keywords in get_custom_tags().items():
        for kw in keywords:
            if _keyword_pattern(kw).search(text_norm):
                matched.append(tag)
                break

    return matched


def tag_article(title: str, summary: str) -> list[str]:
    """Тегирует статью по совокупности заголовка и аннотации."""
    combined = f"{title or ''} {summary or ''}"
    return tag_text(combined)
