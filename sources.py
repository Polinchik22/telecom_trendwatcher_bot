"""
Список источников для сбора статей.
Каждый источник: имя, язык, ссылка на RSS-фид.
"""

SOURCES = [
    # 🇷🇺 Российские отраслевые
    {
        "name": "ComNews",
        "language": "ru",
        "rss_url": "https://www.comnews.ru/rss",
    },
    {
        "name": "NAG.ru",
        "language": "ru",
        "rss_url": "https://nag.ru/rss/all",
    },
    {
        "name": "Хабр / Стандарты связи",
        "language": "ru",
        "rss_url": "https://habr.com/ru/rss/hubs/network_standarts/articles/all/?fl=ru",
    },
    {
        "name": "Ростелеком — новости",
        "language": "ru",
        "rss_url": "https://www.rostelecom.ru/press/news/rss/",
    },

    # 🇬🇧 Англоязычные отраслевые (Tier 1)
    {
        "name": "Light Reading",
        "language": "en",
        "rss_url": "https://www.lightreading.com/rss.xml",
    },
    {
        "name": "Telecoms.com",
        "language": "en",
        "rss_url": "https://telecoms.com/feed/",
    },
    {
        "name": "Total Telecom",
        "language": "en",
        "rss_url": "https://www.totaltele.com/rss",
    },
    {
        "name": "RCR Wireless News",
        "language": "en",
        "rss_url": "https://www.rcrwireless.com/feed",
    },
    {
        "name": "Developing Telecoms",
        "language": "en",
        "rss_url": "https://developingtelecoms.com/feed",
    },

    # 🇬🇧 Технологические / аналитические (Tier 2 + вендоры)
    {
        "name": "IEEE Spectrum — Telecom",
        "language": "en",
        "rss_url": "https://spectrum.ieee.org/feeds/topic/telecom.rss",
    },
    {
        "name": "Ericsson Blog",
        "language": "en",
        "rss_url": "https://www.ericsson.com/en/blog/feed",
    },
    {
        "name": "GSMA Newsroom",
        "language": "en",
        "rss_url": "https://www.gsma.com/newsroom/rss",
    },

    # 📐 Стандартизация
    {
        "name": "3GPP News",
        "language": "en",
        "rss_url": "https://www.3gpp.org/rss",
    },
    {
        "name": "ETSI News",
        "language": "en",
        "rss_url": "https://www.etsi.org/rss",
    },

    # 📰 Пресс-релизы
    {
        "name": "PR Newswire — Telecommunications",
        "language": "en",
        "rss_url": "https://www.prnewswire.com/rss/telecommunications-latest-news.rss",
    },
    {
        "name": "AT&T Newsroom",
        "language": "en",
        "rss_url": "https://www.att.com/RSS",
    },

    # 🇨🇳 Китайские источники (добавлены по вашему примеру)
    {
        "name": "C114 (中国通信网)",
        "language": "chi",
        "rss_url": "http://www.c114.com.cn/rss/",
    },
    {
        "name": "通信世界网",
        "language": "chi",
        "rss_url": "http://www.cww.net.cn/rss/",
    },
]