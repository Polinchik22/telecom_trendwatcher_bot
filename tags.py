"""
Таксономия хештегов: для каждого тега — список ключевых слов и синонимов
(на русском и английском), по которым статья будет считаться относящейся
к этому тегу.

Как добавить новый хештег или ключевое слово — см. ИНСТРУКЦИЯ_ДОБАВЛЕНИЕ_ТЕГОВ.md
"""

TAXONOMY = {
    "2G": ["2g", "второго поколения"],
    "4G": ["4g", "lte", "четвёртого поколения", "четвертого поколения"],
    "5G": ["5g", "пятого поколения", "пятое поколение связи"],
    "5GAdvanced": ["5g-advanced", "5g advanced", "release 18", "3gpp release 18"],
    "6G": ["6g", "шестого поколения", "шестое поколение связи"],
    "OpenRAN": ["open ran", "openran", "o-ran", "открытый ран", "виртуализация радиодоступа", "mavenir"],
    "AIRAN": ["ai-ran", "ai ran", "искусственный интеллект в ran", "ии в радиосети"],
    "NetworkSlicing": ["network slicing", "нарезка сети", "сетевой слайсинг", "слайсинг сети"],
    "RedCap": ["redcap", "reduced capability", "облегчённый 5g"],
    "FTTH": ["ftth", "fiber to the home", "оптика до дома", "волокно до дома", "gpon", "fiber", "оптоволокн*", "оптический кабель", "corning"],
    "IoT": ["iot", "интернет вещей", "internet of things", "умный датчик", "датчики iot"],
    "NB-IoT": ["nb-iot", "narrowband iot", "узкополосный iot"],
    "EdgeComputing": ["edge computing", "периферийные вычисления", "edge-вычисления"],
    "SpaceInternet": ["starlink", "oneweb", "спутниковый интернет", "низкоорбитальные спутники", "leo satellite", "спутниковая связь", "spacemobile", "спутниковый оператор", "satellite launch", "kuiper", "eutelsat", "iridium", "viasat", "direct to device", "прямое подключение к спутнику"],
    "SubseaCables": ["подводный кабель", "подводные кабели", "subsea cable", "submarine cable"],
    "Spectrum": ["спектр частот", "частотный ресурс", "spectrum auction", "аукцион частот", "выделение частот"],
    "M&A": ["слияние", "поглощение", "merger", "acquisition", "сделка по покупке", "сделка по приобретению", "restructures", "реструктуризация", "продажа бизнеса", "sale of business", "divest"],
    "Bankruptcy": ["банкротство", "bankruptcy", "процедура банкротства", "financial distress"],
    "Regulation": ["минцифры", "роскомнадзор", "fcc", "регулятор связи", "закон о связи", "regulation", "gsma", "ofcom", "еврокомиссия", "european commission"],
    "Cybersecurity": ["кибербезопасность", "cybersecurity", "утечка данных", "data breach", "взлом сети", "ddos", "постквантов*", "quantum-safe", "quantum-resistant"],
    "AI": ["искусственный интеллект", "artificial intelligence", "нейросет*", "machine learning", "ии", "llm"],
    "CloudNative": ["cloud native", "облачно-нативн", "контейнеризация", "kubernetes", "nfv", "telco cloud", "телеком-облако"],
    "Hyperscalers": ["aws", "amazon web services", "microsoft azure", "google cloud", "гипермасштабируем*", "hyperscaler"],
    "NetworkAPIs": ["camara", "network api", "сетевые api", "открытые api оператора", "network exposure"],
    "DigitalTwin": ["цифровой двойник", "digital twin"],
    "PrivateNetworks": ["частная сеть связи", "private network", "private 5g", "корпоративная сеть связи", "private wireless"],
    "DataCenter": ["дата-центр", "дата-центры", "data center", "цод"],
    "SmartCity": ["умный город", "smart city"],
    "Roaming": ["роуминг", "roaming"],
    "Tariffs": ["тарифный план", "тарифы на связь", "tariff plan", "субсидия на устройство", "device subsidy", "trade-in", "рассрочка на устройство"],
    "VoLTE": ["volte", "голос по lte"],
    "Wi-Fi": ["wi-fi", "wifi", "вай-фай", "wi-fi 7", "802.11be"],
    "Backbone": ["магистральная сеть", "backbone network"],
    "Vendors": ["huawei", "хуавей", "ericsson", "эрикссон", "nokia", "нокиа", "zte", "cisco", "циско", "поставщик оборудования", "вендор связи", "samsung", "juniper", "nec", "ciena", "adtran"],
    "Operators": ["мтс", "билайн", "мегафон", "ростелеком", "т2", "tele2", "vodafone", "at&t", "verizon", "orange", "deutsche telekom", "оператор связи", "t-mobile", "china mobile", "china telecom", "china unicom", "reliance jio", "bharti airtel", "telefonica", "ntt docomo", "kddi", "singtel", "telstra", "telenor", "kpn", "swisscom", "turkcell", "openreach", "zayo", "nexfibre", "cityfibre"],
    "Broadband": ["широкополосный доступ", "broadband internet", "коаксиал*", "coaxial cable"],
    "eSIM": ["esim", "есим"],
    "Semiconductors": ["чипы", "полупроводник*", "semiconductor", "chipset", "qualcomm", "mediatek", "broadcom", "marvell", "nvidia"],
    "Investment": ["инвестици*", "investment round", "funding round", "венчурн*"],
    "Standards": ["3gpp", "ietf", "стандарт связи", "телекоммуникационный стандарт"],
    "NetworkOutage": ["сбой сети", "авария на сети", "network outage", "network failure", "service restored", "восстановлен после сбоя"],
    "Sustainability": ["устойчивое развитие", "sustainability", "углеродн*", "green telecom"],
    "Quantum": ["квантов*", "quantum communication", "quantum computing"],
    "XR": ["метавселенная", "metaverse", "виртуальная реальность", "дополненная реальность"],
}
