# Telecom Trendwatcher Bot

A Telegram bot that collects telecom news from RSS feeds and helps users explore it by topic or natural-language query.

## What it does

- Collects articles from multilingual RSS sources on a daily schedule.
- Organizes articles by telecom topics and supports custom tags.
- Provides topic summaries, recent articles, and mention trends.
- Stores articles and tags in SQLite.
- Uses an LLM for tasks such as matching free-text questions to topics.

## Commands

| Command | Purpose |
|---|---|
| `/actual` | Show currently active topics |
| `/tags` | List topics in the database |
| `/status` | Show database and source counts |
| `/addtag` | Add a topic |
| `/help` | Show available commands |

You can also search with a hashtag or ask a question in plain language.

## Run locally

1. Install the dependencies:
   ```bash
   pip install -r requirements_v6.txt
   ```
2. Set the Telegram bot token in your shell:
   ```bash
   export BOT_TOKEN="your-token-from-BotFather"
   ```
3. Start the bot:
   ```bash
   python bot_v7.py
   ```

The token is read from the `BOT_TOKEN` environment variable and should not be committed to the repository.

For the detailed architecture and implementation notes, see [ОПИСАНИЕ_ПРОЕКТА.md](ОПИСАНИЕ_ПРОЕКТА.md) (Russian).
