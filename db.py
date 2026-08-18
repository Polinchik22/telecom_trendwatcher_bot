"""
Работа с базой данных статей (SQLite).
База хранится в файле articles.db рядом со скриптом.
"""

import sqlite3
from pathlib import Path

from tags import TAXONOMY

DB_PATH = Path(__file__).parent / "articles.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Создаёт таблицы, если их ещё нет. Вызывается при старте бота."""
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            published_at TEXT,
            language TEXT,
            summary TEXT,
            crawled_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS article_tags (
            article_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            PRIMARY KEY (article_id, tag),
            FOREIGN KEY (article_id) REFERENCES articles(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tag_digests (
            tag TEXT PRIMARY KEY,
            digest TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS custom_tags (
            tag TEXT PRIMARY KEY,
            keywords TEXT NOT NULL,
            added_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def article_exists(url: str) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,)).fetchone()
    conn.close()
    return row is not None


def insert_article(title, source, url, published_at, language, summary):
    """
    Добавляет статью в базу. Если такой url уже есть — тихо пропускает
    (дедупликация). Возвращает id новой статьи, либо None если это дубль.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO articles (title, source, url, published_at, language, summary)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, source, url, published_at, language, summary),
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # url уже есть в базе — статья не новая
        return None
    finally:
        conn.close()


def count_articles():
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM articles").fetchone()
    conn.close()
    return row["cnt"]


def get_custom_tags() -> dict:
    """Все пользовательские теги: {имя_тега: [ключевые слова]}."""
    conn = get_connection()
    rows = conn.execute("SELECT tag, keywords FROM custom_tags").fetchall()
    conn.close()
    return {row["tag"]: row["keywords"].split(",") for row in rows}


def add_custom_tag(tag: str, keywords: list[str], added_by: int = None) -> tuple[bool, str]:
    """
    Добавляет новый пользовательский тег. Отказывает, если такой тег уже
    есть в основном словаре (tags.py) или уже был добавлен раньше.
    Возвращает (успех, текст сообщения для пользователя).
    """
    if tag in TAXONOMY:
        return False, f"Тег #{tag} уже есть в основном словаре бота."

    conn = get_connection()
    existing = conn.execute("SELECT 1 FROM custom_tags WHERE tag = ?", (tag,)).fetchone()
    if existing:
        conn.close()
        return False, f"Тег #{tag} уже был добавлен раньше."

    conn.execute(
        "INSERT INTO custom_tags (tag, keywords, added_by) VALUES (?, ?, ?)",
        (tag, ",".join(keywords), added_by),
    )
    conn.commit()
    conn.close()
    return True, (
        f"✅ Тег #{tag} добавлен!\nКлючевые слова: {', '.join(keywords)}\n\n"
        "Будет применяться автоматически к новым статьям при следующем "
        "сборе. К уже собранным статьям применится, когда разработчик "
        "запустит пересчёт тегов вручную."
    )


def get_all_known_tags() -> dict:
    """Объединённый словарь: встроенные теги (tags.py) + пользовательские."""
    combined = dict(TAXONOMY)
    combined.update(get_custom_tags())
    return combined


def save_tags(article_id: int, tags: list[str]):
    """
    Сохраняет теги для статьи (игнорирует уже существующие пары).
    Дополнительно отфильтровывает всё, чего нет ни в TAXONOMY (tags.py),
    ни в пользовательских тегах — даже если какая-то функция по ошибке
    передаст "сырой" тег, в базу он не попадёт.
    """
    valid_universe = set(TAXONOMY.keys()) | set(get_custom_tags().keys())
    valid_tags = [t for t in tags if t in valid_universe]
    if not valid_tags:
        return
    conn = get_connection()
    conn.executemany(
        "INSERT OR IGNORE INTO article_tags (article_id, tag) VALUES (?, ?)",
        [(article_id, tag) for tag in valid_tags],
    )
    conn.commit()
    conn.close()


def get_tag_counts():
    """Возвращает список (tag, кол-во статей), отсортированный по убыванию."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT tag, COUNT(*) as cnt
        FROM article_tags
        GROUP BY tag
        ORDER BY cnt DESC
        """
    ).fetchall()
    conn.close()
    return [(row["tag"], row["cnt"]) for row in rows]


def get_all_articles_for_tagging():
    """Возвращает все статьи (id, title, summary) — используется для ретро-тегирования."""
    conn = get_connection()
    rows = conn.execute("SELECT id, title, summary FROM articles").fetchall()
    conn.close()
    return [(row["id"], row["title"], row["summary"]) for row in rows]


def count_tagged_articles():
    """Сколько уникальных статей имеют хотя бы один тег."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(DISTINCT article_id) as cnt FROM article_tags"
    ).fetchone()
    conn.close()
    return row["cnt"]


def get_source_counts():
    """Сколько статей собрано по каждому источнику, по убыванию."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT source, COUNT(*) as cnt
        FROM articles
        GROUP BY source
        ORDER BY cnt DESC
        """
    ).fetchall()
    conn.close()
    return [(row["source"], row["cnt"]) for row in rows]


def get_untagged_articles_full(limit: int = 200):
    """То же самое, но с аннотацией — нужно для LLM-тегирования."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, title, summary, source FROM articles
        WHERE id NOT IN (SELECT article_id FROM article_tags)
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [(row["id"], row["title"], row["summary"], row["source"]) for row in rows]


def get_untranslated_articles(limit: int = 200):
    """
    Статьи, у которых язык источника не 'ru' и не 'en' — то есть их ещё
    нужно перевести на английский (например, китайские источники).
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, title, summary FROM articles
        WHERE language NOT IN ('ru', 'en')
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    return [(row["id"], row["title"], row["summary"]) for row in rows]


def update_article_translation(article_id: int, title: str, summary: str):
    """
    Сохраняет переведённые заголовок и аннотацию. Заодно помечает язык
    статьи как 'en', чтобы повторный /translate её не трогал.
    """
    conn = get_connection()
    conn.execute(
        "UPDATE articles SET title = ?, summary = ?, language = 'en' WHERE id = ?",
        (title, summary, article_id),
    )
    conn.commit()
    conn.close()


def delete_invalid_tags(valid_tags: list[str]) -> int:
    """
    Удаляет из article_tags все теги, которых нет в переданном списке
    допустимых (valid_tags). Используется один раз для очистки "мусорных"
    тегов, которые раньше попадали в базу напрямую из RSS-категорий
    источников (не из словаря tags.py). Возвращает количество удалённых
    строк.
    """
    conn = get_connection()
    placeholders = ",".join("?" for _ in valid_tags)
    cursor = conn.execute(
        f"DELETE FROM article_tags WHERE tag NOT IN ({placeholders})",
        valid_tags,
    )
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return deleted


def save_tag_digest(tag: str, digest: str):
    """Сохраняет (или обновляет) дайджест по теме — пересчитывается раз в сутки."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO tag_digests (tag, digest, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(tag) DO UPDATE SET digest = excluded.digest, updated_at = CURRENT_TIMESTAMP
        """,
        (tag, digest),
    )
    conn.commit()
    conn.close()


def get_tag_digest(tag: str):
    """Возвращает закэшированный дайджест по теме, либо None если его ещё нет."""
    conn = get_connection()
    row = conn.execute("SELECT digest FROM tag_digests WHERE tag = ?", (tag,)).fetchone()
    conn.close()
    return row["digest"] if row else None


def get_tags_needing_digest_refresh():
    """
    Возвращает теги, у которых появилась хотя бы одна новая статья
    с момента последнего пересчёта дайджеста (или дайджеста ещё нет
    вообще). Используется, чтобы не пересчитывать дайджест впустую для
    тем, где со вчера ничего не изменилось.
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT t.tag
        FROM (
            SELECT at.tag AS tag, MAX(a.crawled_at) AS last_article
            FROM article_tags at
            JOIN articles a ON a.id = at.article_id
            GROUP BY at.tag
        ) t
        LEFT JOIN tag_digests d ON d.tag = t.tag
        WHERE d.tag IS NULL OR d.updated_at < t.last_article
        """
    ).fetchall()
    conn.close()
    return [row["tag"] for row in rows]


def get_distinct_tags():
    """Все уникальные теги, которые реально встречаются в базе."""
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT tag FROM article_tags").fetchall()
    conn.close()
    return [row["tag"] for row in rows]


def get_database_age_days():
    """Сколько дней прошло с самой первой собранной статьи. None, если статей ещё нет."""
    conn = get_connection()
    row = conn.execute(
        "SELECT (julianday('now') - julianday(MIN(crawled_at))) as age FROM articles"
    ).fetchone()
    conn.close()
    return row["age"] if row and row["age"] is not None else None


def get_trending_tags(limit: int = 3, period_days: int = 7):
    """
    Возвращает теги, у которых сейчас наибольший прирост статей за
    period_days дней по сравнению с предыдущим таким же периодом.

    ВАЖНО: сравнение "к предыдущему периоду" требует минимум 2*period_days
    дней истории в базе. Если бот работает меньше этого срока, "предыдущий
    период" физически не существует (данных о нём нет, а не 0 статей по
    теме) — раньше это ошибочно засчитывалось как "новая тема" для ВСЕХ
    тегов подряд. Пока истории не хватает, честно переключаемся на простой
    рейтинг активности (сколько статей вышло за period_days), без
    сравнения с прошлым — это не "тренд", а "что сейчас активно обсуждают".
    """
    conn = get_connection()
    db_age = get_database_age_days()
    has_enough_history = db_age is not None and db_age >= period_days * 2

    tags = [row["tag"] for row in conn.execute("SELECT DISTINCT tag FROM article_tags").fetchall()]

    results = []
    for tag in tags:
        current = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM articles a
            JOIN article_tags t ON a.id = t.article_id
            WHERE t.tag = ? AND a.crawled_at >= datetime('now', ?)
            """,
            (tag, f"-{period_days} days"),
        ).fetchone()["cnt"]

        if current == 0:
            continue

        if not has_enough_history:
            # Недостаточно истории для честного сравнения — ранжируем
            # просто по числу статей за период, без ярлыка "новая тема".
            results.append({
                "tag": tag, "current": current, "previous": None,
                "score": current, "pct": None, "insufficient_history": True,
            })
            continue

        previous = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM articles a
            JOIN article_tags t ON a.id = t.article_id
            WHERE t.tag = ?
              AND a.crawled_at >= datetime('now', ?)
              AND a.crawled_at < datetime('now', ?)
            """,
            (tag, f"-{period_days * 2} days", f"-{period_days} days"),
        ).fetchone()["cnt"]

        if previous == 0:
            score = float("inf")
            pct = None
        else:
            score = (current - previous) / previous
            pct = round(score * 100)

        results.append({
            "tag": tag, "current": current, "previous": previous,
            "score": score, "pct": pct, "insufficient_history": False,
        })

    conn.close()
    results.sort(key=lambda r: (r["score"], r["current"]), reverse=True)
    return results[:limit]


def get_articles_by_tag(tag: str, limit: int = 5):
    """Последние статьи по конкретному тегу (сортировка по времени сбора)."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT a.title, a.source, a.url, a.published_at, a.crawled_at
        FROM articles a
        JOIN article_tags t ON a.id = t.article_id
        WHERE t.tag = ?
        ORDER BY a.crawled_at DESC
        LIMIT ?
        """,
        (tag, limit),
    ).fetchall()
    conn.close()
    return rows


def get_tag_dynamics(tag: str):
    """
    Считает динамику упоминаемости тега за неделю/месяц/квартал.
    Важно: используется дата СБОРА статьи (crawled_at), а не дата публикации —
    даты публикации у разных источников приходят в разных форматах и не
    всегда надёжно парсятся, а crawled_at всегда единообразна. Для прототипа
    это разумное упрощение: пока бот работает недолго, "собрано" ≈ "вышло".
    """
    conn = get_connection()
    periods = {"неделя": 7, "месяц": 30, "квартал": 90}
    result = {}

    for label, days in periods.items():
        current = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM articles a
            JOIN article_tags t ON a.id = t.article_id
            WHERE t.tag = ? AND a.crawled_at >= datetime('now', ?)
            """,
            (tag, f"-{days} days"),
        ).fetchone()["cnt"]

        previous = conn.execute(
            """
            SELECT COUNT(*) as cnt FROM articles a
            JOIN article_tags t ON a.id = t.article_id
            WHERE t.tag = ?
              AND a.crawled_at >= datetime('now', ?)
              AND a.crawled_at < datetime('now', ?)
            """,
            (tag, f"-{days * 2} days", f"-{days} days"),
        ).fetchone()["cnt"]

        pct_change = None
        if previous > 0:
            pct_change = round((current - previous) / previous * 100)

        result[label] = {"count": current, "previous": previous, "pct_change": pct_change}

    conn.close()
    return result
