"""
Разовая проверка: ищет в кэше дайджестов (tag_digests) записи с
китайскими символами — такое могло остаться от дайджестов, посчитанных
ДО фикса перевода (когда статья ошибочно считалась переведённой).
Удаляет такие записи из кэша — они автоматически пересчитаются заново
при следующем /collect, уже из корректно переведённых статей.

Запуск: python3 check_digests.py
"""

import re
from db import get_connection, init_db

CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

init_db()
conn = get_connection()
rows = conn.execute("SELECT tag, digest FROM tag_digests").fetchall()

found = [r for r in rows if CJK_PATTERN.search(r["digest"] or "")]

print(f"Всего дайджестов в кэше: {len(rows)}")
print(f"С китайскими символами: {len(found)}\n")

for r in found:
    print(f"#{r['tag']}: {r['digest'][:80]}")

if found:
    tags = [r["tag"] for r in found]
    conn.executemany("DELETE FROM tag_digests WHERE tag = ?", [(t,) for t in tags])
    conn.commit()
    print(f"\nУдалила {len(tags)} дайджест(ов) из кэша — пересчитаются заново при следующем /collect.")
else:
    print("Китайских символов в дайджестах не найдено 🎉")

conn.close()
