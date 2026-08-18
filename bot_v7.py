"""
Телеком-трендвотчер — минимальный набор команд для пользователя,
вся техническая часть (сбор, теги, перевод, дайджесты) работает
автоматически и в фоне. Устойчив к обрывам сети до Telegram (ретраи +
увеличенные тайм-ауты).
"""

import asyncio
import logging
from telegram import Update, ReplyKeyboardMarkup
from telegram.error import TimedOut, NetworkError
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

from db import init_db, get_tag_counts, count_articles, count_tagged_articles, get_source_counts, add_custom_tag
from crawler import (
    run_full_pipeline,
    collect_all,
    translate_existing_articles,
    llm_tag_untagged,
    compute_all_digests,
)
from hashtag_search import find_matching_tag, build_hashtag_report, build_actual_report
from llm_client import llm_match_query, llm_generate_keywords

# ==== ВСТАВЬ СВОЙ ТОКЕН СЮДА (между кавычками) ====
BOT_TOKEN = "8794997220:AAE1jqBr2OQH80dXJb677MuQiEhGIBXYpZ8"
# ====================================================

# /collect — тяжёлая команда (сбор + перевод + LLM-теги + дайджесты),
# доступна только тебе как разработчику. Узнать свой numeric ID можно у
# бота @userinfobot в Telegram — напиши ему /start, он пришлёт твой ID.
ADMIN_USER_ID = 301870367  # <-- впиши сюда свой числовой ID, например 123456789

COLLECT_INTERVAL_SECONDS = 86400

WELCOME_TEXT = (
    "Привет! Я телеком-трендвотчер 📡\n\n"
    "Напиши #хештег или просто вопрос своими словами — пойму, о чём "
    "речь, и покажу свежие статьи, дайджест и динамику.\n\n"
    "Команды:\n"
    "/actual — 3 самые актуальные (быстрорастущие) темы прямо сейчас\n"
    "/tags — список тем, по которым есть статьи\n"
    "/status — сколько статей в базе, с тегами и по каждому источнику\n"
    "/addtag — добавить новый тег, если нужной темы ещё нет\n"
    "/help — справка\n\n"
    "Кнопки внизу — быстрый доступ к основным действиям, всегда под рукой."
)

# Постоянная панель кнопок под полем ввода — не нужно помнить команды.
# /collect сюда не входит: это разработческая команда, не для обычного
# использования (она тяжёлая и может занимать много времени).
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["/actual 🔥", "/tags 🏷"],
        ["/status 📊", "/addtag"],
        ["/help ❓"],
    ],
    resize_keyboard=True,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Пользователи, которые вызвали /addtag без аргументов и должны следующим
# сообщением прислать имя тега. Простое множество в памяти процесса —
# состояние живёт, пока бот запущен, сбрасывается при перезапуске
# (это ожидаемо для короткого диалогового шага, не для долгого состояния).
pending_addtag_users: set[int] = set()


async def safe_reply(update: Update, text: str, **kwargs):
    """
    Обёртка над reply_text с повторными попытками. Сеть до Telegram
    иногда бывает нестабильной (ConnectTimeout) — без ретраев сообщение
    просто теряется навсегда, даже если бот всё честно посчитал.
    Пробует до 3 раз с небольшой паузой между попытками.
    """
    for attempt in range(3):
        try:
            await update.message.reply_text(text, **kwargs)
            return
        except (TimedOut, NetworkError) as e:
            logger.warning("Не удалось отправить сообщение (попытка %s/3): %s", attempt + 1, e)
            if attempt < 2:
                await asyncio.sleep(3)
    logger.error("Сообщение так и не отправилось после 3 попыток: %r", text[:200])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update, WELCOME_TEXT, reply_markup=MAIN_KEYBOARD)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(
        update,
        "Доступные команды:\n"
        "/start — приветствие и список функций\n"
        "/actual — 3 самые актуальные (быстрорастущие) темы прямо сейчас\n"
        "/tags — список тем, по которым есть статьи\n"
        "/status — сколько статей в базе, с тегами и по каждому источнику\n"
        "/addtag — добавить новый тег, если нужной темы ещё нет\n"
        "/help — эта справка\n\n"
        "Также можно написать #хештег (например #5G) или просто вопрос "
        "своими словами — LLM подберёт ближайший тег.\n\n"
        "Сбор новых статей, теги, перевод и дайджесты по темам обновляются "
        "автоматически раз в сутки — вручную запускать ничего не нужно.\n\n"
        "/collect — есть ещё одна команда, но она доступна только "
        "разработчику бота.",
        reply_markup=MAIN_KEYBOARD,
    )


async def collect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_USER_ID is None or update.effective_user.id != ADMIN_USER_ID:
        await safe_reply(update, "Эта команда доступна только разработчику бота.")
        return

    await safe_reply(
        update,
        "Обновляю статьи, теги, переводы и дайджесты — это может занять "
        "несколько минут, не закрывай бота. Буду присылать статус по "
        "каждому этапу отдельно."
    )

    # Каждый этап отправляется отдельным сообщением сразу после завершения —
    # так разбивка по источникам точно долетает до чата, даже если
    # какой-то из следующих этапов упадёт по сети или по ошибке.
    try:
        stage = await asyncio.to_thread(collect_all)
        await safe_reply(update, stage)
    except Exception as e:
        logger.exception("Ошибка на этапе сбора статей")
        await safe_reply(update, f"⚠️ Сбор статей упал с ошибкой: {e}")
        return

    try:
        stage = await asyncio.to_thread(translate_existing_articles)
        await safe_reply(update, stage)
    except Exception as e:
        logger.exception("Ошибка на этапе перевода")
        await safe_reply(update, f"⚠️ Перевод упал с ошибкой: {e}")

    try:
        stage = await asyncio.to_thread(llm_tag_untagged)
        await safe_reply(update, stage)
    except Exception as e:
        logger.exception("Ошибка на этапе LLM-разметки")
        await safe_reply(update, f"⚠️ LLM-разметка упала с ошибкой: {e}")

    try:
        stage = await asyncio.to_thread(compute_all_digests)
        await safe_reply(update, stage)
    except Exception as e:
        logger.exception("Ошибка на этапе дайджестов")
        await safe_reply(update, f"⚠️ Дайджесты упали с ошибкой: {e}")

    await safe_reply(update, "✅ Обновление полностью завершено.")


async def _do_addtag(update: Update, tag_name: str, keywords: list[str] | None):
    """
    Общая логика добавления тега — используется и когда всё пришло в
    одной команде (/addtag Web3 ...), и когда имя тега пришло отдельным
    сообщением после диалогового /addtag.
    """
    tag_name = tag_name.replace(" ", "")
    auto_generated = keywords is None

    if auto_generated:
        await safe_reply(update, f"Подбираю ключевые слова для #{tag_name} через LLM, подожди немного...")
        keywords = await asyncio.to_thread(llm_generate_keywords, tag_name)
        if not keywords:
            await safe_reply(
                update,
                "Не получилось подобрать ключевые слова автоматически "
                "(возможно, Ollama сейчас недоступна). Можешь задать их сама:\n"
                f"/addtag {tag_name} ключевое слово 1, ключевое слово 2",
            )
            return

    success, message = add_custom_tag(tag_name, keywords, update.effective_user.id)
    if success and auto_generated:
        message += "\n\n(ключевые слова подобрала LLM автоматически)"
    await safe_reply(update, message)


async def addtag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /addtag — бот попросит написать имя тега следующим сообщением
    (без повторного вызова команды).
    /addtag ИмяТега — сразу же добавляет, LLM подбирает ключевые слова.
    /addtag ИмяТега ключевое слово 1, ключевое слово 2 — вручную.
    """
    text = update.message.text
    parts = text.split(maxsplit=1)

    if len(parts) < 2:
        # Аргументов нет — переходим в режим ожидания следующего сообщения
        pending_addtag_users.add(update.effective_user.id)
        await safe_reply(
            update,
            "Хорошо! Напиши следующим сообщением название тега (одно слово "
            "или короткая фраза) — я сама подберу ключевые слова и добавлю его.",
        )
        return

    rest = parts[1].strip()

    if "," in rest:
        name_and_rest = rest.split(maxsplit=1)
        if len(name_and_rest) < 2:
            await safe_reply(update, "Нужно и имя тега, и хотя бы одно ключевое слово через запятую.")
            return
        tag_name, keywords_raw = name_and_rest
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
        await _do_addtag(update, tag_name, keywords)
    else:
        await _do_addtag(update, rest, None)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = count_articles()
    tagged = count_tagged_articles()
    source_counts = get_source_counts()

    lines = [f"📊 Сейчас в базе: {total} статей.", f"Из них с тегами: {tagged}.", ""]
    if source_counts:
        lines.append("По источникам:")
        for source, count in source_counts:
            lines.append(f"  • {source}: {count}")

    await safe_reply(update, "\n".join(lines))


async def tags_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tag_counts = get_tag_counts()
    if not tag_counts:
        await safe_reply(update, "Статей пока нет — жди автосбор (раз в сутки).")
        return
    lines = [f"#{tag} — {count}" for tag, count in tag_counts[:40]]
    text = "🏷 Темы и количество статей:\n\n" + "\n".join(lines)
    await safe_reply(update, text)


async def actual_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    report = build_actual_report()
    await safe_reply(update, report, parse_mode="HTML", disable_web_page_preview=True)


async def hashtag_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает любое текстовое сообщение:
    - #хештег из словаря/синонимов -> сразу показываем отчёт
    - #хештег, которого нет -> просим LLM понять, к чему это ближе
    - обычный текст без # -> сразу отдаём его LLM как запрос на естественном языке
    """
    text = update.message.text.strip()

    if update.effective_user.id in pending_addtag_users:
        pending_addtag_users.discard(update.effective_user.id)
        await _do_addtag(update, text, None)
        return

    if text.startswith("#"):
        tag = find_matching_tag(text)
        if tag is not None:
            report = build_hashtag_report(tag)
            await safe_reply(update, report, parse_mode="HTML", disable_web_page_preview=True)
            return

        await safe_reply(update, "Не нашла точный тег, спрашиваю у модели, подожди...")
        guessed = await asyncio.to_thread(llm_match_query, text.lstrip("#"))
        if guessed is None:
            suggested_name = text.lstrip("#").strip().title().replace(" ", "")
            await safe_reply(
                update,
                f"Тег {text} не нашла и не смогла сопоставить ни с одним известным. "
                "Посмотри /tags — там список тем, которые реально есть у статей.\n\n"
                f"Хочешь добавить новый тег? Напиши:\n"
                f"/addtag {suggested_name}\n"
                "(я сама подберу ключевые слова через LLM)",
            )
            return

        report = build_hashtag_report(guessed)
        await safe_reply(
            update,
            f"Точного совпадения нет, но по смыслу это похоже на #{guessed}:\n\n" + report,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return

    await safe_reply(update, "Ищу подходящую тему, подожди немного...")
    guessed = await asyncio.to_thread(llm_match_query, text)
    if guessed is None:
        suggested_name = text.strip().title().replace(" ", "")[:30]
        await safe_reply(
            update,
            "Не поняла запрос и не смогла подобрать подходящую тему. "
            "Попробуй написать #хештег или посмотри /tags.\n\n"
            f"Хочешь добавить новый тег для этой темы? Напиши:\n"
            f"/addtag {suggested_name}\n"
            "(я сама подберу ключевые слова через LLM)",
        )
        return

    report = build_hashtag_report(guessed)
    await safe_reply(
        update,
        f"Похоже, ты имеешь в виду #{guessed}:\n\n" + report,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def scheduled_pipeline(context: ContextTypes.DEFAULT_TYPE):
    """Раз в сутки: сбор + перевод + LLM-теги + дайджесты."""
    logger.info("Запускаю автоматический цикл обновления...")
    try:
        report = await asyncio.to_thread(run_full_pipeline)
        logger.info(report)
    except Exception:
        logger.exception("Автоматический цикл обновления упал с ошибкой")


def main():
    if BOT_TOKEN == "ВСТАВЬ_СЮДА_ТОКЕН_ОТ_BOTFATHER":
        print("⚠️  Ты забыл(а) вставить токен в файл bot.py!")
        return

    init_db()

    # Увеличенные тайм-ауты — терпимее к нестабильной сети до Telegram.
    # Это НЕ замедляет обычную работу: тайм-аут — это верхний предел
    # ожидания на случай проблем, а не искусственная задержка.
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("collect", collect_command))
    app.add_handler(CommandHandler("addtag", addtag_command))
    app.add_handler(CommandHandler("tags", tags_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("actual", actual_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, hashtag_message))

    app.job_queue.run_repeating(scheduled_pipeline, interval=COLLECT_INTERVAL_SECONDS, first=30)

    print("Бот запущен. Открой Telegram и напиши ему /start")
    print("Чтобы остановить бота — нажми Ctrl+C")
    app.run_polling()


if __name__ == "__main__":
    main()
