"""
Разовая проверка: ищет в базе статьи, где остался непереведённый
китайский текст (и вообще любые CJK-иероглифы), и по желанию помечает
их на повторный перевод при следующем /collect.

Запуск: python3 check_chinese.py
"""

import re
from db import get_connection, init_db

CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

init_db()
conn = get_connection()
rows = conn.execute("SELECT id, title, summary, source, language FROM articles").fetchall()

found = [
    r for r in rows
    if CJK_PATTERN.search(r["title"] or "") or CJK_PATTERN.search(r["summary"] or "")
]

print(f"Всего статей в базе: {len(rows)}")
print(f"С китайскими символами: {len(found)}\n")

for r in found[:30]:
    print(f"[id={r['id']}] [{r['source']}] [язык в базе: {r['language']}] {r['title'][:70]}")

if found:
    print("\nСтавлю эти статьи в очередь на повторный перевод...")
    ids = [r["id"] for r in found]
    conn.executemany("UPDATE articles SET language = 'zh' WHERE id = ?", [(i,) for i in ids])
    conn.commit()
    print(f"Готово — {len(ids)} статей будут переведены при следующем /collect.")
else:
    print("Китайских символов не найдено 🎉")

conn.close()
