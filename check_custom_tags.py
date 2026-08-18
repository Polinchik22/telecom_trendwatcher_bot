"""
Разовая проверка: показывает ВСЕ пользовательские теги из базы,
независимо от того, есть у них статьи или нет — чтобы точно увидеть,
сохранился тег на самом деле или нет.

Запуск: python3 check_custom_tags.py
"""

from db import get_connection, init_db

init_db()
conn = get_connection()

rows = conn.execute(
    """
    SELECT c.tag, c.keywords, c.created_at,
           COUNT(t.article_id) as article_count
    FROM custom_tags c
    LEFT JOIN article_tags t ON t.tag = c.tag
    GROUP BY c.tag
    ORDER BY c.created_at DESC
    """
).fetchall()

if not rows:
    print("В базе нет ни одного пользовательского тега.")
else:
    print(f"Всего пользовательских тегов: {len(rows)}\n")
    for r in rows:
        print(f"#{r['tag']} — добавлен {r['created_at']}, статей: {r['article_count']}")
        print(f"    ключевые слова: {r['keywords']}")

conn.close()
