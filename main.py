from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
import httpx
import os
import re
import json
import uuid
import base64
import secrets
import asyncio
import asyncpg
from bs4 import BeautifulSoup
from urllib.parse import urlparse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_SUBSCRIBE_CODE = os.environ.get("TELEGRAM_SUBSCRIBE_CODE", "")
BROADCAST_SECRET = os.environ.get("BROADCAST_SECRET", "")
DEMO_BOT_TOKEN = os.environ.get("DEMO_BOT_TOKEN", "")
DEMO_WEBHOOK_SECRET = os.environ.get("DEMO_WEBHOOK_SECRET", "")
ALERTS_BOT_TOKEN = os.environ.get("ALERTS_BOT_TOKEN", "")
ALERTS_WEBHOOK_SECRET = os.environ.get("ALERTS_WEBHOOK_SECRET", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")  # для авторегистрации webhook

SYSTEM = """Ты — AI-консультант на сайте компании «Первый ИИ» (pervyyii.ru).
Компания создаёт и внедряет AI-агентов для российского бизнеса.

# КТО ТЫ
Ты сам — живой пример того, что продаёт компания. Своей работой ты
показываешь, каким может быть агент клиента. Поэтому отвечай умно,
спокойно и по делу — ты витрина.

# КАК ТЫ ОБЩАЕШЬСЯ
- На «вы», тепло, но по-деловому. Без навязчивости и давления.
- Сначала польза: пойми задачу клиента, дай ценный ответ.
  Продажа — следствие, а не цель каждой фразы.
- Коротко. 2-4 предложения. Без воды и канцелярита.
- Если клиент готов — мягко веди к заявке.

# ЧТО ТЫ ЗНАЕШЬ О КОМПАНИИ
Услуга: AI-агент, который отвечает клиентам 24/7, собирает заявки,
не пропускает обращения. Внедрение за 7 дней. Код со стороны
клиента не нужен — всё техническое делает «Первый ИИ».

Как работает внедрение (3 шага):
1. Разбор бизнеса — часовой созвон про услуги, частые вопросы, цены, стиль.
2. Настройка и обучение — логика, база знаний, подключение к сайту,
   тест на 50+ сценариях.
3. Запуск и поддержка — ежемесячная доработка по реальным диалогам.

Тарифы:
- Старт — 29 000 ₽ единоразово + 4 900 ₽/мес. До 1 500 диалогов/мес,
  интеграция на сайт, уведомления о заявках в Telegram.
- Про (популярный) — 59 000 ₽ + 9 900 ₽/мес. Всё из Старта + квиз,
  калькулятор стоимости, обучение на вашем контенте, до 3 000 диалогов,
  ежемесячная доработка.
- Премиум — 129 000 ₽ + 22 900 ₽/мес. Всё из Про + CRM/Битрикс24,
  до 10 000 диалогов, дашборд аналитики, приоритетная поддержка 24/7.
- Индивидуальный — от 199 000 ₽, состав и помесячная поддержка
  определяются по итогам разбора. Для бизнеса со сложными задачами:
  мультиканальность (сайт + Telegram + WhatsApp + Авито), глубокая
  интеграция с CRM и каталогом, несколько агентов под разные задачи,
  обучение команды клиента, выделенная поддержка. Точную цену называть
  нельзя — всегда говорить «от 199 000 ₽, итог после часового разбора».

Дополнительные услуги (отдельные продукты, не входят в тарифы выше):
- Голосовой приёмщик звонков — от 129 000 ₽ + 14 900 ₽/мес. AI отвечает
  на пропущенные звонки, узнаёт что нужно клиенту, заводит лид в
  Telegram. Подключаем к Манго / Sipuni / UIS.
- WhatsApp-агент — от 59 000 ₽ + 8 900 ₽/мес. Тот же агент, но в
  WhatsApp Business. Отвечает 24/7, собирает заявки. ВАЖНО: клиенту
  нужен подключённый WhatsApp Business API — это отдельная подписка
  Meta, оплачивается напрямую (мы не посредники). Если спросят про
  стоимость WA Business API — честно говори «зависит от объёма
  диалогов, обычно сотни рублей в месяц для малого бизнеса, точную
  схему расскажем на созвоне».
- Авито-агент — от 59 000 ₽ + 8 900 ₽/мес. Отвечает на сообщения
  в Авито за 30 секунд, 24/7. Фильтрует мусор («ещё актуально?»),
  отдаёт реальные лиды в Telegram. Скорость ответа поднимает
  ранжирование объявлений в выдаче Авито. ВАЖНО: с конца 2025 Авито
  открывает доступ к API мессенджера только на платных тарифах —
  клиенту нужен активный тариф Авито (Расширенный от 2 000 ₽/мес или
  Максимальный от 4 000 ₽/мес в зависимости от категории). Это
  оплачивается Авито напрямую, не нами. Большинство активных
  продавцов на Авито такой тариф уже имеют независимо от ИИ-агента.
- Ответы на отзывы — от 12 900 ₽/мес (подписка, без единоразового
  платежа). Мониторим 2ГИС, Яндекс.Карты, Авито. AI отвечает в тоне
  бренда, негатив прилетает владельцу в Telegram.
- Контент для соцсетей — от 39 900 ₽/мес (подписка). Поток постов,
  сторис и рилсов под бренд. Темник согласуем в Telegram.

По доп. услугам точные сроки и итоговую цену называть нельзя — всегда
говорить «обсудим по часовому созвону, итог индивидуально». Если клиент
заинтересовался — собирай заявку (имя + контакт).

Ниши: дизайн интерьера, салоны красоты, юр. услуги, недвижимость,
стоматология, образование, фитнес, рестораны — любая, где есть
повторяющиеся вопросы клиентов.

Виджет вставляется за 5 минут, работает с Tilda, Bitrix, WordPress
и любым конструктором.

# ЦЕЛЬ ДИАЛОГА
Помочь клиенту понять, подойдёт ли ему агент, и мягко подвести к заявке.
Для заявки нужно собрать: имя, телефон или Telegram, сферу бизнеса.
Когда клиент согласен — попроси эти данные и скажи, что ответят в течение 2 часов.

# ЧЕГО НЕ ДЕЛАТЬ
- Не выдумывай цены, сроки и возможности, которых нет выше.
- Не дави и не уговаривай. Если клиент не готов — предложи подумать.
- Если не знаешь ответа — честно скажи, что уточнит менеджер,
  и предложи оставить контакт.
- Не обсуждай темы вне работы компании.

# ЯЗЫК И ОФОРМЛЕНИЕ
- Пиши грамотным русским языком, проверяй слова. Например: «заинтересованные»,
  а не «интересованные»; «принять решение», а не «решиться принять».
- Если выделяешь термин или цифру — используй markdown **жирным**. Списки —
  обычными тире. Не злоупотребляй выделениями, максимум 2-3 на сообщение."""


# ─────────────────── Demo bot (public Telegram) ───────────────────

DEMO_GREETING = (
    "Здравствуйте! Я — живая демонстрация AI-агента, которого делает компания "
    "«Первый ИИ» (pervyyii.ru).\n\n"
    "Назовите *вашу нишу одним сообщением* — и через несколько секунд я покажу "
    "3 диалога, как такой агент будет разговаривать с *вашими* клиентами.\n\n"
    "Примеры, что написать:\n"
    "— автосервис в Москве, шиномонтаж\n"
    "— ремонт квартир под ключ\n"
    "— загородное строительство, каркасные дома\n"
    "— кухни на заказ, замер и проект\n\n"
    "Жду вашу нишу 👇"
)

DEMO_SYSTEM = """Ты — Telegram-бот @pervyyii_demo_bot. Живая демонстрация AI-агентов компании «Первый ИИ» (pervyyii.ru), которая делает AI-агентов для российского бизнеса.

# ГЛАВНАЯ ЗАДАЧА
Когда человек называет свою нишу — покажи живое демо: сгенерируй 3 короткие сценки-диалога, как агент, сделанный под его бизнес, говорил бы с его реальными клиентами. Цель — чтобы человек увидел готовый продукт под себя, а не слушал абстрактные обещания.

# ФОРМАТ ПЕРВОГО ДЕМО
После первого осмысленного сообщения с нишей бизнеса отвечаешь строго так:

«Готовый агент для [ниша] говорил бы вашим клиентам так:

━━━━━━━━━━━━━━━━━
*Сцена 1. [короткое название — типичный запрос]*

— [реплика клиента, естественная, по-человечески]
— [реплика агента: коротко, на «вы», по делу]
— [клиент уточняет / возражает]
— [агент решает: записывает, считает, переводит на мастера]

━━━━━━━━━━━━━━━━
*Сцена 2. [возражение про цену или сомнение]*
…

━━━━━━━━━━━━━━━━
*Сцена 3. [ночное обращение или сложный запрос — то, что человек руками не успевает]*
…
━━━━━━━━━━━━━━━━

Понравилось? Соберу такого же агента под ваш бизнес за 7 дней. Просто напишите сюда — прямо в этот чат — ваше имя и телефон (или Telegram-ник), и команда свяжется с вами в течение 2 часов.»

# ПРАВИЛА ДЕМО-СЦЕН
- Сцены ДОЛЖНЫ быть конкретными под нишу: реальные названия услуг, типичные возражения, реалистичные вилки цен (пиши «от X ₽» или «обычно Y», не выдумывай точные цифры).
- Агент в сценах общается как живой человек: коротко, на «вы», без канцелярита и роботизмов.
- Третья сцена показывает «то, что руками невозможно»: ночное обращение, два клиента одновременно, сложный возврат, забытая запись.
- Каждая сцена — 4-6 реплик, не больше. Не растягивай.
- Не используй имена клиентов в сценах («— Здравствуйте, я Иван...»). Только содержательные реплики.

# ПОСЛЕ ДЕМО
Если человек оставил имя и контакт (телефон или Telegram-юзернейм):
→ Поблагодари тепло и коротко: «Спасибо, [имя]! Получил заявку. Свяжусь с вами в течение 2 часов лично.» Больше ничего не пиши, не предлагай ещё демо.

Если человек задаёт вопросы про услугу — отвечай как консультант, коротко (2-4 предложения):
- Внедрение под ключ за 7 дней.
- Тарифы агента на сайт: Старт 29 000 ₽ + 4 900 ₽/мес, Про 59 000 ₽ + 9 900 ₽/мес, Премиум 129 000 ₽ + 22 900 ₽/мес, Индивидуальный от 199 000 ₽.
- Виджет ставится на сайт за 5 минут (Tilda, Bitrix24, WordPress, любой конструктор).
- Доп. услуги (отдельные продукты): голосовой агент на звонки от 129 000 ₽ + 14 900/мес, WhatsApp-агент от 59 000 ₽ + 8 900/мес, Авито-агент от 59 000 ₽ + 8 900/мес, ответы на отзывы от 12 900 ₽/мес (подписка), контент для соцсетей от 39 900 ₽/мес (подписка). По ним — точную цену не называй, говори «обсудим на созвоне».
- Уведомления о заявках в Telegram владельцу — во всех тарифах от Старта. Агент в Telegram-боте для общения с клиентами — Премиум. WhatsApp / Авито — Индивидуальный или отдельные услуги.
- CRM-интеграция (Битрикс24, AmoCRM) — Премиум и выше.
- Ежемесячная доработка по реальным диалогам входит во все тарифы.

Если человек хочет демо для ДРУГОЙ ниши — сделай новое полноценное демо в том же формате.

Если человек пишет что-то непонятное (одно слово, эмодзи, бессмыслицу) — мягко переспроси: «Расскажите коротко о вашем бизнесе — какая ниша, что продаёте? Тогда покажу демо.»

# ЯЗЫК И СТИЛЬ
- Только русский, без англицизмов где есть нормальные русские слова.
- Эмодзи — крайне сдержанно, максимум один на сообщение.
- Telegram Markdown: *жирный* (одна звёздочка, не две), _курсив_, `код`. Списки — обычными тире.
- Не используй ## заголовки, **двойные звёздочки**, --- горизонтальные линии — Telegram их не рендерит как markdown. Только то, что выше.

# ЧЕГО НЕ ДЕЛАТЬ
- Не давай скидок и не торгуйся.
- Не обещай сроки конкретнее «7 дней».
- Не упоминай слова «промпт», «API», «GPT», «Claude», «нейросеть», «искусственный интеллект» в долгих рассуждениях. Ты просто умный агент.
- Не задавай больше 1 вопроса в сообщении.
- Не пиши длинные послесловия после демо — после трёх сцен только короткий призыв оставить контакт.
- Не обсуждай темы вне работы компании."""


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    user_agent TEXT,
    referrer TEXT,
    ip TEXT,
    business_niche TEXT,
    tariff_interest TEXT,
    intent_summary TEXT,
    lead_name TEXT,
    lead_contact TEXT,
    has_lead BOOLEAN DEFAULT FALSE,
    lead_notified BOOLEAN DEFAULT FALSE,
    msg_count INTEGER DEFAULT 0,
    last_extracted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_read INTEGER
);

CREATE TABLE IF NOT EXISTS telegram_subscribers (
    chat_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    subscribed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts_subscribers (
    chat_id BIGINT NOT NULL,
    source TEXT NOT NULL,
    username TEXT,
    first_name TEXT,
    subscribed_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (chat_id, source)
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_lead ON sessions(has_lead) WHERE has_lead = TRUE;
CREATE INDEX IF NOT EXISTS idx_alerts_source ON alerts_subscribers(source);
"""


pool: asyncpg.Pool | None = None


@app.on_event("startup")
async def startup() -> None:
    global pool
    if not DATABASE_URL:
        print("[startup] DATABASE_URL not set — analytics disabled")
        return
    try:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
        async with pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)
        print("[startup] DB pool ready, schema applied")
        await _register_alerts_webhook()
    except Exception as e:
        print(f"[startup] DB init failed: {e}")
        pool = None


@app.on_event("shutdown")
async def shutdown() -> None:
    if pool:
        await pool.close()


# ─────────────────── Telegram ───────────────────

async def tg_send(text: str) -> None:
    """Send a message to all telegram subscribers. Fire-and-forget; never raises."""
    if not (TELEGRAM_BOT_TOKEN and pool):
        return
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT chat_id FROM telegram_subscribers")
        if not rows:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            for r in rows:
                try:
                    await client.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                        json={"chat_id": r["chat_id"], "text": text, "parse_mode": "HTML"},
                    )
                except Exception as e:
                    print(f"[tg] send to {r['chat_id']} failed: {e}")
    except Exception as e:
        print(f"[tg] tg_send failed: {e}")


@app.post("/telegram/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if not TELEGRAM_WEBHOOK_SECRET or not secrets.compare_digest(secret, TELEGRAM_WEBHOOK_SECRET):
        raise HTTPException(404)
    if not pool:
        return {"ok": True}
    update = await request.json()
    msg = update.get("message") or update.get("edited_message") or {}
    text = (msg.get("text") or "").strip()
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return {"ok": True}
    if text.startswith("/start"):
        # Require correct subscription code; silently ignore otherwise so
        # the bot doesn't reveal itself to random visitors.
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else ""
        if not TELEGRAM_SUBSCRIBE_CODE or not secrets.compare_digest(code, TELEGRAM_SUBSCRIBE_CODE):
            return {"ok": True}
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO telegram_subscribers (chat_id, username, first_name)
                       VALUES ($1, $2, $3)
                       ON CONFLICT (chat_id) DO UPDATE
                       SET username=EXCLUDED.username, first_name=EXCLUDED.first_name""",
                    chat_id, chat.get("username"), chat.get("first_name"),
                )
            await _tg_send_to(chat_id, "Подписаны на уведомления о новых лидах с pervyyii.ru ✓")
        except Exception as e:
            print(f"[tg] /start failed: {e}")
    elif text.startswith("/stop"):
        try:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM telegram_subscribers WHERE chat_id=$1", chat_id)
            await _tg_send_to(chat_id, "Отписаны от уведомлений.")
        except Exception as e:
            print(f"[tg] /stop failed: {e}")
    return {"ok": True}


async def _tg_send_to(chat_id: int, text: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
    except Exception as e:
        print(f"[tg] direct send failed: {e}")


# ─────────────────── Alerts bot (external clients) ───────────────────

async def _register_alerts_webhook() -> None:
    """Set the alerts bot webhook to our public URL on startup. No-op if not configured."""
    if not (ALERTS_BOT_TOKEN and ALERTS_WEBHOOK_SECRET and PUBLIC_BASE_URL):
        return
    url = f"{PUBLIC_BASE_URL.rstrip('/')}/alerts/webhook/{ALERTS_WEBHOOK_SECRET}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{ALERTS_BOT_TOKEN}/setWebhook",
                json={"url": url, "allowed_updates": ["message"]},
            )
            data = r.json()
            if data.get("ok"):
                print(f"[alerts] webhook set: {url}")
            else:
                print(f"[alerts] setWebhook failed: {data}")
    except Exception as e:
        print(f"[alerts] webhook registration failed: {e}")


async def _alerts_send_to(chat_id: int, text: str, parse_mode: str | None = "HTML") -> None:
    if not ALERTS_BOT_TOKEN:
        return
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{ALERTS_BOT_TOKEN}/sendMessage",
                json=payload,
            )
            if r.status_code >= 400 and parse_mode:
                payload.pop("parse_mode", None)
                await client.post(
                    f"https://api.telegram.org/bot{ALERTS_BOT_TOKEN}/sendMessage",
                    json=payload,
                )
    except Exception as e:
        print(f"[alerts] send to {chat_id} failed: {e}")


async def alerts_send(source: str, text: str) -> None:
    """Send a message to all subscribers of a specific source. Fire-and-forget."""
    if not (ALERTS_BOT_TOKEN and pool and source):
        return
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT chat_id FROM alerts_subscribers WHERE source=$1",
                source,
            )
        for r in rows:
            await _alerts_send_to(r["chat_id"], text)
    except Exception as e:
        print(f"[alerts] alerts_send failed: {e}")


@app.post("/alerts/webhook/{secret}")
async def alerts_webhook(secret: str, request: Request):
    if not ALERTS_WEBHOOK_SECRET or not secrets.compare_digest(secret, ALERTS_WEBHOOK_SECRET):
        raise HTTPException(404)
    if not pool:
        return {"ok": True}
    update = await request.json()
    msg = update.get("message") or update.get("edited_message") or {}
    text = (msg.get("text") or "").strip()
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return {"ok": True}

    if text.startswith("/start"):
        # Deep-link: /start <source>. If no source — explain how to subscribe.
        parts = text.split(maxsplit=1)
        source = parts[1].strip().lower() if len(parts) > 1 else ""
        if not source or not source.replace("-", "").replace("_", "").isalnum() or len(source) > 32:
            await _alerts_send_to(
                chat_id,
                "Привет! Это бот уведомлений «Первого ИИ» — сюда приходят заявки "
                "с сайтов, на которых работает наш AI-помощник.\n\n"
                "Чтобы подключиться, откройте персональную ссылку, "
                "которую вам прислали — она содержит код подключения "
                "(пример: <code>?start=ваш_сайт</code>).\n\n"
                "Если ссылка не сработала, перешлите её ещё раз и нажмите "
                "кнопку «Start» внутри Telegram.",
            )
            return {"ok": True}
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO alerts_subscribers (chat_id, source, username, first_name)
                       VALUES ($1, $2, $3, $4)
                       ON CONFLICT (chat_id, source) DO UPDATE
                       SET username=EXCLUDED.username, first_name=EXCLUDED.first_name""",
                    chat_id, source, chat.get("username"), chat.get("first_name"),
                )
            await _alerts_send_to(
                chat_id,
                f"Подключено ✓\n\nВы будете получать заявки с сайта "
                f"<b>{source}</b> прямо сюда. "
                f"Каждая новая заявка — отдельным сообщением.",
            )
        except Exception as e:
            print(f"[alerts] /start failed: {e}")
            await _alerts_send_to(chat_id, "Не удалось подключить. Попробуйте позже.", parse_mode=None)

    elif text.startswith("/stop"):
        try:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM alerts_subscribers WHERE chat_id=$1", chat_id)
            await _alerts_send_to(chat_id, "Отключено. Уведомления больше не приходят.", parse_mode=None)
        except Exception as e:
            print(f"[alerts] /stop failed: {e}")

    return {"ok": True}


# ─────────────────── Demo bot (public) ───────────────────

async def demo_send(chat_id: int, text: str, parse_mode: str | None = "Markdown") -> None:
    """Send a message via the public demo bot. Falls back to plain text if markdown breaks."""
    if not DEMO_BOT_TOKEN:
        return
    payload = {"chat_id": chat_id, "text": text[:4000]}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{DEMO_BOT_TOKEN}/sendMessage",
                json=payload,
            )
            if r.status_code >= 400 and parse_mode:
                # markdown parsing likely failed — retry as plain text
                payload.pop("parse_mode", None)
                await client.post(
                    f"https://api.telegram.org/bot{DEMO_BOT_TOKEN}/sendMessage",
                    json=payload,
                )
    except Exception as e:
        print(f"[demo] send failed: {e}")


async def demo_typing(chat_id: int) -> None:
    if not DEMO_BOT_TOKEN:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"https://api.telegram.org/bot{DEMO_BOT_TOKEN}/sendChatAction",
                json={"chat_id": chat_id, "action": "typing"},
            )
    except Exception:
        pass


@app.post("/demo/webhook/{secret}")
async def demo_webhook(secret: str, request: Request):
    if not DEMO_WEBHOOK_SECRET or not secrets.compare_digest(secret, DEMO_WEBHOOK_SECRET):
        raise HTTPException(404)
    if not (DEMO_BOT_TOKEN and ANTHROPIC_API_KEY):
        return {"ok": True}

    update = await request.json()
    msg = update.get("message") or update.get("edited_message") or {}
    text = (msg.get("text") or "").strip()
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return {"ok": True}

    # Ignore non-text (stickers, photos, voice) with a gentle nudge
    if not text:
        await demo_send(chat_id, "Я понимаю только текст. Напишите вашу нишу одним сообщением — покажу демо.")
        return {"ok": True}

    # Cap incoming length defensively
    text = text[:2000]
    session_id = f"tg_demo_{chat_id}"
    username = chat.get("username") or ""
    first_name = chat.get("first_name") or ""
    user_label = f"@{username}" if username else first_name or str(chat_id)

    # /start — reset session and greet
    if text == "/start" or text.startswith("/start "):
        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute("DELETE FROM messages WHERE session_id=$1", session_id)
                    await conn.execute(
                        """INSERT INTO sessions (session_id, user_agent, referrer, ip)
                           VALUES ($1, 'telegram', $2, '')
                           ON CONFLICT (session_id) DO UPDATE
                           SET last_activity_at=NOW(),
                               has_lead=FALSE, lead_notified=FALSE,
                               msg_count=0, referrer=EXCLUDED.referrer""",
                        session_id, f"@pervyyii_demo_bot ← {user_label}",
                    )
            except Exception as e:
                print(f"[demo] /start db reset failed: {e}")
        await demo_send(chat_id, DEMO_GREETING)
        return {"ok": True}

    # /help — short instructions
    if text == "/help":
        await demo_send(
            chat_id,
            "Просто напишите вашу нишу одним сообщением — например *«автосервис»* или "
            "*«репетитор по математике»* — и я покажу 3 диалога, как агент будет говорить "
            "с вашими клиентами.\n\nКоманды:\n/start — начать заново\n/help — эта подсказка",
        )
        return {"ok": True}

    # Regular conversational turn
    if not pool:
        await demo_send(chat_id, "Сервис временно недоступен. Попробуйте позже.")
        return {"ok": True}

    try:
        async with pool.acquire() as conn:
            history = await conn.fetch(
                "SELECT role, content FROM messages WHERE session_id=$1 ORDER BY created_at LIMIT 40",
                session_id,
            )
            await conn.execute(
                """INSERT INTO sessions (session_id, user_agent, referrer, ip)
                   VALUES ($1, 'telegram', $2, '')
                   ON CONFLICT (session_id) DO UPDATE SET last_activity_at=NOW()""",
                session_id, f"@pervyyii_demo_bot ← {user_label}",
            )
            await conn.execute(
                "INSERT INTO messages (session_id, role, content) VALUES ($1, 'user', $2)",
                session_id, text[:8000],
            )
    except Exception as e:
        print(f"[demo] db pre-call failed: {e}")
        history = []

    await demo_typing(chat_id)

    messages_for_claude = [{"role": r["role"], "content": r["content"]} for r in history]
    messages_for_claude.append({"role": "user", "content": text})

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": 1500,
                    "system": [
                        {
                            "type": "text",
                            "text": DEMO_SYSTEM,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    "messages": messages_for_claude,
                },
            )
            data = response.json()
    except httpx.HTTPError as e:
        print(f"[demo] upstream failed: {e}")
        await demo_send(chat_id, "Связь с моделью прервалась. Попробуйте отправить ещё раз через минуту.")
        return {"ok": True}

    if "error" in data:
        print(f"[demo] anthropic error: {data['error']}")
        await demo_send(chat_id, "Что-то пошло не так на моей стороне. Попробуйте ещё раз через минуту.")
        return {"ok": True}

    content = data.get("content") or []
    reply = "".join(b.get("text", "") for b in content if b.get("type") == "text").strip()
    if not reply:
        await demo_send(chat_id, "Не получилось сгенерировать ответ. Попробуйте переформулировать.")
        return {"ok": True}

    usage = data.get("usage") or {}
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO messages
                    (session_id, role, content, input_tokens, output_tokens, cache_read)
                   VALUES ($1, 'assistant', $2, $3, $4, $5)""",
                session_id, reply[:8000],
                usage.get("input_tokens"), usage.get("output_tokens"),
                usage.get("cache_read_input_tokens"),
            )
            await conn.execute(
                "UPDATE sessions SET msg_count = msg_count + 2, last_activity_at = NOW() WHERE session_id=$1",
                session_id,
            )
        asyncio.create_task(extract_metadata(session_id, source="Telegram-демо-бота"))
    except Exception as e:
        print(f"[demo] db post-call failed: {e}")

    await demo_send(chat_id, reply)
    return {"ok": True}


# ─────────────────── Metadata extraction ───────────────────

EXTRACTION_SYSTEM = """Ты обрабатываешь диалог посетителя сайта с AI-агентом, который продаёт услугу AI-агентов для бизнеса.

Извлеки структурированные данные. Верни СТРОГО валидный JSON, без markdown, без комментариев, в одну строку или с переносами. Поля:

{
  "business_niche": одна из строк ["дизайн интерьера","салон красоты","юр.услуги","недвижимость","медицина","образование","фитнес","рестораны","ритейл","автоуслуги","строительство","ивенты","IT","другое","не определено"],
  "tariff_interest": одна из ["Старт","Про","Премиум","Индивидуальный","Голосовой агент","WhatsApp-агент","Авито-агент","Ответы на отзывы","Контент для соцсетей","несколько","не определено"],
  "intent_summary": строка 1-2 предложения, что человек спрашивал и чего хочет,
  "has_lead": true ТОЛЬКО если человек явно оставил имя И контакт (телефон или telegram). Если оставил только имя или только сферу — false.,
  "lead_name": имя или null,
  "lead_contact": контакт или null
}"""


async def extract_metadata(session_id: str, source: str = "pervyyii.ru") -> None:
    """Background: read transcript, ask LLM for structured fields, update sessions row.
    Also fires Telegram notification on first lead detection. `source` is shown in the TG message."""
    if not (pool and ANTHROPIC_API_KEY):
        return
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT role, content FROM messages WHERE session_id=$1 ORDER BY created_at LIMIT 40",
                session_id,
            )
            sess = await conn.fetchrow(
                "SELECT has_lead, lead_notified FROM sessions WHERE session_id=$1",
                session_id,
            )
        if not rows:
            return
        transcript = "\n\n".join(f"[{r['role']}] {r['content']}" for r in rows)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 400,
                    "system": EXTRACTION_SYSTEM,
                    "messages": [{"role": "user", "content": transcript}],
                },
            )
            data = response.json()
        text = "".join(b.get("text", "") for b in (data.get("content") or []) if b.get("type") == "text").strip()
        # tolerate ```json fences if model wraps anyway
        if text.startswith("```"):
            text = text.strip("`").lstrip("json").strip()
        extracted = json.loads(text)
        has_lead_new = bool(extracted.get("has_lead"))
        async with pool.acquire() as conn:
            await conn.execute(
                """UPDATE sessions SET
                    business_niche=$2, tariff_interest=$3, intent_summary=$4,
                    has_lead=$5, lead_name=$6, lead_contact=$7, last_extracted_at=NOW()
                   WHERE session_id=$1""",
                session_id,
                extracted.get("business_niche") or "не определено",
                extracted.get("tariff_interest") or "не определено",
                extracted.get("intent_summary"),
                has_lead_new,
                extracted.get("lead_name"),
                extracted.get("lead_contact"),
            )
        # Fire TG notification on transition false → true
        if has_lead_new and not (sess and sess["lead_notified"]):
            niche = extracted.get("business_niche") or "—"
            name = extracted.get("lead_name") or "—"
            contact = extracted.get("lead_contact") or "—"
            tariff = extracted.get("tariff_interest") or "—"
            summary = extracted.get("intent_summary") or ""
            await tg_send(
                f"🎯 <b>Новый лид с {source}</b>\n\n"
                f"<b>Имя:</b> {name}\n"
                f"<b>Контакт:</b> {contact}\n"
                f"<b>Сфера:</b> {niche}\n"
                f"<b>Интерес к тарифу:</b> {tariff}\n\n"
                f"<i>{summary}</i>"
            )
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE sessions SET lead_notified=TRUE WHERE session_id=$1", session_id
                )
    except Exception as e:
        print(f"[extract] failed for {session_id}: {e}")


# ─────────────────── Chat ───────────────────

@app.post("/chat")
async def chat(request: Request):
    if not ANTHROPIC_API_KEY:
        return JSONResponse(
            {"error": "ANTHROPIC_API_KEY is not configured on the server"},
            status_code=500,
        )

    body = await request.json()
    messages = body.get("messages", [])
    if not messages:
        return JSONResponse({"error": "messages is empty"}, status_code=400)

    session_id = body.get("session_id") or str(uuid.uuid4())
    referrer = body.get("referrer") or ""
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "").split(",")[0].strip()
    user_agent = request.headers.get("user-agent", "")[:500]

    # Log user message (the last one in history is what they just sent)
    last_user = messages[-1] if messages else None
    if pool and last_user and last_user.get("role") == "user":
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO sessions (session_id, user_agent, referrer, ip)
                       VALUES ($1, $2, $3, $4)
                       ON CONFLICT (session_id) DO UPDATE SET last_activity_at=NOW()""",
                    session_id, user_agent, referrer[:500], ip[:64],
                )
                await conn.execute(
                    "INSERT INTO messages (session_id, role, content) VALUES ($1, 'user', $2)",
                    session_id, str(last_user.get("content", ""))[:8000],
                )
        except Exception as e:
            print(f"[chat] db log user msg failed: {e}")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 2000,
                    "system": [
                        {
                            "type": "text",
                            "text": SYSTEM,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    "messages": messages,
                },
            )
            data = response.json()
    except httpx.HTTPError as e:
        return JSONResponse({"error": f"upstream request failed: {e}"}, status_code=502)

    if "error" in data:
        return JSONResponse({"error": data["error"]}, status_code=response.status_code or 500)

    content = data.get("content") or []
    text_parts = [block.get("text", "") for block in content if block.get("type") == "text"]
    reply = "".join(text_parts).strip()
    if not reply:
        return JSONResponse({"error": "empty reply from model", "raw": data}, status_code=502)

    usage = data.get("usage") or {}

    # Log assistant reply + update counters + kick off background extraction
    if pool:
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO messages
                        (session_id, role, content, input_tokens, output_tokens, cache_read)
                       VALUES ($1, 'assistant', $2, $3, $4, $5)""",
                    session_id, reply[:8000],
                    usage.get("input_tokens"), usage.get("output_tokens"),
                    usage.get("cache_read_input_tokens"),
                )
                await conn.execute(
                    """UPDATE sessions SET msg_count = msg_count + 2, last_activity_at = NOW()
                       WHERE session_id=$1""",
                    session_id,
                )
            asyncio.create_task(extract_metadata(session_id))
        except Exception as e:
            print(f"[chat] db log assistant msg failed: {e}")

    return JSONResponse({"reply": reply, "usage": usage, "session_id": session_id})


# ─────────────────── Admin ───────────────────

def require_admin(request: Request) -> None:
    if not ADMIN_PASSWORD:
        raise HTTPException(503, "Admin not configured")
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("basic "):
        raise HTTPException(401, headers={"WWW-Authenticate": 'Basic realm="admin"'})
    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8", errors="ignore")
        _, _, pwd = decoded.partition(":")
    except Exception:
        raise HTTPException(401, headers={"WWW-Authenticate": 'Basic realm="admin"'})
    if not secrets.compare_digest(pwd, ADMIN_PASSWORD):
        raise HTTPException(401, headers={"WWW-Authenticate": 'Basic realm="admin"'})


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    require_admin(request)
    try:
        return FileResponse("admin.html")
    except Exception:
        return HTMLResponse("<h1>admin.html not found</h1>", status_code=500)


@app.get("/admin/data")
async def admin_data(request: Request):
    require_admin(request)
    if not pool:
        return JSONResponse({"error": "database not configured"}, status_code=503)
    async with pool.acquire() as conn:
        sessions = await conn.fetch(
            """SELECT session_id, created_at, last_activity_at, msg_count,
                      business_niche, tariff_interest, intent_summary,
                      has_lead, lead_name, lead_contact, referrer, ip, user_agent
               FROM sessions
               ORDER BY created_at DESC
               LIMIT 1000"""
        )
        stats = await conn.fetchrow(
            """SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE has_lead) AS leads,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 day') AS today,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') AS week
               FROM sessions"""
        )
        subs = await conn.fetch(
            "SELECT chat_id, username, first_name, subscribed_at FROM telegram_subscribers ORDER BY subscribed_at DESC"
        )
    return {
        "stats": dict(stats) if stats else {},
        "sessions": [
            {
                **dict(s),
                "created_at": s["created_at"].isoformat() if s["created_at"] else None,
                "last_activity_at": s["last_activity_at"].isoformat() if s["last_activity_at"] else None,
            }
            for s in sessions
        ],
        "telegram_subscribers": len(subs),
        "subscribers": [
            {
                "chat_id": str(s["chat_id"]),
                "username": s["username"],
                "first_name": s["first_name"],
                "subscribed_at": s["subscribed_at"].isoformat() if s["subscribed_at"] else None,
            }
            for s in subs
        ],
    }


@app.delete("/admin/subscriber/{chat_id}")
async def admin_unsubscribe(chat_id: int, request: Request):
    require_admin(request)
    if not pool:
        return JSONResponse({"error": "database not configured"}, status_code=503)
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM telegram_subscribers WHERE chat_id=$1", chat_id)
    return {"ok": True, "deleted": result.split()[-1] if result else "0"}


@app.get("/admin/session/{session_id}")
async def admin_session_detail(session_id: str, request: Request):
    require_admin(request)
    if not pool:
        return JSONResponse({"error": "database not configured"}, status_code=503)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT role, content, created_at FROM messages
               WHERE session_id=$1 ORDER BY created_at""",
            session_id,
        )
    return [
        {"role": r["role"], "content": r["content"], "created_at": r["created_at"].isoformat()}
        for r in rows
    ]


# ─────────────────── Public ───────────────────

@app.post("/broadcast")
async def broadcast(request: Request):
    """Receive a lead notification from a client backend and fan out via Telegram.
    Auth: X-Broadcast-Secret header matching BROADCAST_SECRET env.

    Routing:
      - route="family" (default): family hub bot @pervyyii_leads_bot, all subscribers
      - route="alerts": alerts bot, only subscribers of `source`
    """
    if not BROADCAST_SECRET:
        raise HTTPException(503, "broadcast not configured")
    if not secrets.compare_digest(request.headers.get("x-broadcast-secret", ""), BROADCAST_SECRET):
        raise HTTPException(401, "bad secret")
    payload = await request.json()
    source = (payload.get("source") or "—").lower()
    source_display = payload.get("source_display") or payload.get("source") or "—"
    name = payload.get("name") or "—"
    contact = payload.get("contact") or "—"
    niche = payload.get("niche") or "—"
    tariff = payload.get("tariff") or "—"
    summary = payload.get("summary") or ""
    route = (payload.get("route") or "family").lower()

    text = (
        f"🎯 <b>Новая заявка с {source_display}</b>\n\n"
        f"<b>Имя:</b> {name}\n"
        f"<b>Контакт:</b> {contact}\n"
        f"<b>Кто/Сфера:</b> {niche}\n"
        f"<b>Интерес:</b> {tariff}\n\n"
        f"<i>{summary}</i>"
    )

    if route == "alerts":
        await alerts_send(source, text)
    else:
        await tg_send(text)

    return {"ok": True}


# ─────────────────── Audit (lead-magnet) ───────────────────

AUDIT_SYSTEM = """Ты — старший консультант агентства «Первый ИИ» (pervyyii.ru),
которое делает AI-агентов для российского малого и среднего бизнеса.
Тебе дают текст и метаданные конкретного сайта. Твоя задача — найти
ровно 5 КОНКРЕТНЫХ проблем, которые мешают этому сайту приносить
больше заявок. Не общие фразы про «современный дизайн» — а наблюдения
с цитатами и числами из самого сайта.

# КАК ДУМАТЬ
- Смотри глазами посетителя малого бизнеса в РФ. Что мешает оставить
  заявку прямо сейчас.
- Каждая проблема — либо про доверие, либо про скорость отклика, либо
  про прозрачность (цены, сроки, кейсы), либо про вопросы без ответа,
  либо про неудобство первого шага.
- Один из 5 пунктов обязательно — про то, что у сайта нет AI-агента /
  онлайн-консультанта, который отвечает 24/7. Это наш продукт.

# ЧТО УМЕЕТ ПРОДУКТ «ПЕРВЫЙ ИИ» (упоминай только это в fix)
- AI-агент в виде чата на сайте: отвечает текстом 24/7, знает услуги,
  цены, сроки, отвечает на вопросы, собирает контакт и передаёт лид
  в Telegram владельца.
- Может работать так же в Telegram и WhatsApp (отдельная опция).
- НЕ умеет: общаться голосом, звонить, делать дизайн, делать видео.
  Не выдумывай функционал.

# ВАЖНОЕ ОГРАНИЧЕНИЕ
Ты видишь только текст со страницы. JavaScript-виджеты (плавающие чаты,
кнопки мессенджеров, всплывающие формы) могут быть на сайте, но в текст
не попадают. Поэтому:
- НИКОГДА не утверждай «на сайте нет чата / нет онлайн-консультанта /
  нет агента». Ты этого не можешь знать.
- Если хочешь поднять тему AI-агента 24/7 — формулируй её через
  УЛУЧШЕНИЕ: «если у вас уже стоит чат, убедитесь что он отвечает
  моментально и знает все услуги; если нет — поставьте». Без обвинения.
- НИКОГДА не утверждай «нет формы заявки», «нет телефона» и т.п., если
  в данных про каналы связи это не подтверждено явно.

# ЧЕГО НЕЛЬЗЯ ДЕЛАТЬ
- НЕ выдумывай статистику и проценты. Не пиши «60-70% заявок теряется»,
  «X% посетителей уходят» — у тебя нет этих данных. Говори качественно:
  «много обращений ночью», «значительная часть аудитории», без цифр.
- НЕ ссылайся на служебные поля из входных данных («поле X: False»).
  Эти флаги — для твоей ориентации, не упоминай их в evidence.
- НЕ выдумывай детали сайта, которых нет в тексте, который тебе дали.
  Если каких-то данных нет — так и пиши: «на главной нет упоминания…».
- НЕ называй конкретных конкурентов и брендов.

# ФОРМАТ ОТВЕТА
Строго JSON, без префиксов и пояснений, по схеме:
{
  "summary": "одно предложение про сайт в целом — что заметно сразу",
  "problems": [
    {
      "title": "короткий заголовок проблемы (до 60 символов)",
      "evidence": "что именно я увидел на сайте — цитата или факт со страницы",
      "impact": "как это бьёт по выручке/заявкам — качественно, без выдуманных цифр",
      "fix": "что предлагает Первый ИИ — особенно как агент это закрывает"
    }
  ]
}

Ровно 5 объектов в problems. На русском. Без эмодзи. Без markdown.

# ПРАВИЛО КАВЫЧЕК
В значениях полей (evidence, impact, fix, summary, title) используй
только русские кавычки: «ёлочки» для основной речи и „лапки" — для
цитат внутри цитат. Прямую двойную кавычку " не используй внутри
значений никогда — она ломает JSON. Если на сайте было " — заменяй
на «».
"""


def _clean_html_to_text(html: str, limit: int = 8000) -> dict:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()

    title = (soup.title.string or "").strip() if soup.title else ""
    meta_desc = ""
    md = soup.find("meta", attrs={"name": "description"})
    if md and md.get("content"):
        meta_desc = md["content"].strip()

    h1s = [h.get_text(" ", strip=True) for h in soup.find_all("h1")][:5]
    h2s = [h.get_text(" ", strip=True) for h in soup.find_all("h2")][:10]

    has_form = bool(soup.find("form"))
    has_phone = bool(re.search(r"(\+7|8\s?\(?9\d{2}|tel:)", html))
    has_email = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", html))
    has_whatsapp = "wa.me" in html or "whatsapp" in html.lower()
    has_telegram = "t.me/" in html or "telegram" in html.lower()
    has_chat_widget = any(s in html.lower() for s in ["jivo", "talk-me", "carrotquest", "verbox", "intercom"])

    body_text = soup.get_text(" ", strip=True)
    body_text = re.sub(r"\s+", " ", body_text)
    if len(body_text) > limit:
        body_text = body_text[:limit] + " […обрезано]"

    return {
        "title": title,
        "meta_desc": meta_desc,
        "h1s": h1s,
        "h2s": h2s,
        "has_form": has_form,
        "has_phone": has_phone,
        "has_email": has_email,
        "has_whatsapp": has_whatsapp,
        "has_telegram": has_telegram,
        "has_chat_widget": has_chat_widget,
        "body_text": body_text,
    }


def _normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    p = urlparse(raw)
    if not p.netloc or "." not in p.netloc:
        return ""
    return raw


_audit_rate: dict[str, list[float]] = {}


def _rate_limited(ip: str, limit: int = 10, window: int = 3600) -> bool:
    import time
    now = time.time()
    bucket = [t for t in _audit_rate.get(ip, []) if now - t < window]
    if len(bucket) >= limit:
        _audit_rate[ip] = bucket
        return True
    bucket.append(now)
    _audit_rate[ip] = bucket
    return False


@app.post("/audit")
async def audit(request: Request):
    if not ANTHROPIC_API_KEY:
        return JSONResponse({"error": "ANTHROPIC_API_KEY is not configured"}, status_code=500)

    body = await request.json()
    url = _normalize_url(body.get("url", ""))
    if not url:
        return JSONResponse({"error": "Укажите корректный адрес сайта"}, status_code=400)

    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "").split(",")[0].strip() or "unknown"
    if ip not in ("127.0.0.1", "::1", "localhost", "unknown") and _rate_limited(ip):
        return JSONResponse({"error": "Слишком много запросов. Попробуйте через час."}, status_code=429)

    ua_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }

    # Пробуем https → https без verify → http (на случай сломанной HTTPS-конфигурации)
    candidates = [(url, True), (url, False)]
    if url.startswith("https://"):
        candidates.append((url.replace("https://", "http://", 1), True))

    site_html = ""
    site_url = url
    site_ok = False
    for candidate_url, verify in candidates:
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True, verify=verify) as client:
                resp = await client.get(candidate_url, headers=ua_headers)
            if resp.status_code < 400:
                site_html = resp.text
                site_url = str(resp.url)
                site_ok = True
                break
        except httpx.HTTPError:
            continue

    parsed = _clean_html_to_text(site_html) if site_html else _clean_html_to_text("<html></html>")

    # Fallback на Jina Reader: либо нам отказали, либо это SPA с пустым HTML.
    # Передаём в Jina тот URL, который реально открылся (или исходный, если ничего не вышло).
    jina_text = ""
    jina_status = "skipped"
    if not site_ok or len(parsed["body_text"]) < 500:
        try:
            jina_headers = {"Accept": "text/plain", "X-Return-Format": "text"}
            jina_key = os.environ.get("JINA_API_KEY", "")
            if jina_key:
                # С ключом включаем полноценный браузерный рендер для SPA
                jina_headers["Authorization"] = f"Bearer {jina_key}"
                jina_headers["X-Engine"] = "browser"
                jina_headers["X-Timeout"] = "30"
                jina_headers["X-No-Cache"] = "true"
            async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
                jina = await client.get(f"https://r.jina.ai/{site_url}", headers=jina_headers)
                jina_status = f"http_{jina.status_code}_len_{len(jina.text or '')}"
                # Меньше 500 символов = заглушка/ошибка/баннер, не реальный контент
                if jina.status_code < 400 and jina.text and len(jina.text) >= 500:
                    jina_text = jina.text[:8000]
        except httpx.HTTPError as e:
            jina_status = f"error_{type(e).__name__}"

    # Если сайт SPA (HTML пустой) и Jina не помогла — честно говорим, не врём
    if site_ok and len(parsed["body_text"]) < 500 and not jina_text:
        return JSONResponse(
            {"error": "Сайт построен на технологии, которую анализатор пока не разбирает (React/Vue/Next без серверного рендера). Попробуйте позже — мы работаем над этим."},
            status_code=422,
        )

    if not site_ok and not jina_text:
        return JSONResponse(
            {"error": "Не получилось открыть сайт. Проверьте адрес и доступность."},
            status_code=502,
        )

    if jina_text:
        body_for_prompt = jina_text
        flag_source = jina_text
        source_note = "Источник: текст со страницы (рендер SPA через внешний reader)"
    else:
        body_for_prompt = parsed["body_text"] or "(текст не извлечён)"
        flag_source = site_html
        source_note = "Источник: HTML страницы"

    has_phone = bool(re.search(r"(\+7|8[\s\-]?\(?9\d{2}|tel:)", flag_source))
    has_email = bool(re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", flag_source))
    has_whatsapp = "wa.me" in flag_source.lower() or "whatsapp" in flag_source.lower()
    has_telegram = "t.me/" in flag_source.lower() or "telegram" in flag_source.lower()

    channels = []
    if parsed["has_form"]: channels.append("форма заявки")
    if has_phone: channels.append("телефон")
    if has_email: channels.append("email")
    if has_whatsapp: channels.append("WhatsApp")
    if has_telegram: channels.append("Telegram")
    if parsed["has_chat_widget"]: channels.append("сторонний чат-виджет")
    channels_line = ", ".join(channels) if channels else "ничего из этого не найдено"

    user_message = (
        f"URL: {url}\n"
        f"Title: {parsed['title']}\n"
        f"Meta description: {parsed['meta_desc']}\n"
        f"H1: {' | '.join(parsed['h1s']) or '(нет)'}\n"
        f"H2: {' | '.join(parsed['h2s']) or '(нет)'}\n"
        f"Каналы связи на странице: {channels_line}.\n\n"
        f"{source_note}:\n{body_for_prompt}"
    )

    async def call_model(extra_hint: str = "") -> tuple[dict | None, dict, int]:
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-6",
                        "max_tokens": 2500,
                        "system": AUDIT_SYSTEM,
                        "messages": [
                            {"role": "user", "content": user_message + extra_hint},
                        ],
                    },
                )
                return response.json(), {}, response.status_code
        except httpx.HTTPError as e:
            return None, {"error": f"upstream failed: {e}"}, 502

    def extract_json(text: str) -> dict | None:
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
        i, j = raw.find("{"), raw.rfind("}")
        if i < 0 or j < i:
            return None
        chunk = raw[i:j+1]
        for variant in (chunk, re.sub(r",(\s*[}\]])", r"\1", chunk)):
            try:
                return json.loads(variant)
            except json.JSONDecodeError:
                continue
        return None

    result = None
    last_data = None
    for attempt in range(2):
        hint = (
            "\n\nВЕРНИ СТРОГО ОДИН JSON-ОБЪЕКТ, БЕЗ ТЕКСТА ДО ИЛИ ПОСЛЕ. "
            "В значениях используй только русские кавычки «ёлочки» и „лапки“, "
            "прямую двойную кавычку не используй."
        ) if attempt else ""
        data, err, status = await call_model(hint)
        if err:
            return JSONResponse(err, status_code=status)
        last_data = data
        if "error" in data:
            return JSONResponse({"error": data["error"]}, status_code=status or 500)
        parts = [b.get("text", "") for b in (data.get("content") or []) if b.get("type") == "text"]
        result = extract_json("".join(parts))
        if result and isinstance(result.get("problems"), list) and result["problems"]:
            break

    if not result or not isinstance(result.get("problems"), list) or not result["problems"]:
        print(f"[AUDIT] FAIL url={url} ip={ip} reason=bad_json site_ok={site_ok} jina={jina_status}", flush=True)
        return JSONResponse({"error": "Не удалось разобрать ответ модели — попробуйте ещё раз"}, status_code=502)

    titles = " | ".join((p.get("title") or "").strip() for p in result["problems"][:5])
    print(
        f"[AUDIT] OK url={url} ip={ip} site_ok={site_ok} jina={jina_status} "
        f"summary={(result.get('summary') or '').strip()[:200]} titles={titles[:400]}",
        flush=True,
    )

    return JSONResponse({
        "url": url,
        **result,
        "usage": (last_data or {}).get("usage", {}),
        "debug": {"site_ok": site_ok, "html_text_len": len(parsed["body_text"]), "jina": jina_status},
    })


@app.get("/")
async def root():
    return {"status": "ok", "service": "Pervyyii AI Agent"}


@app.get("/health")
async def health():
    return {"status": "ok", "db": "up" if pool else "down"}


@app.get("/agent.html")
async def agent_page():
    return FileResponse("agent.html")
