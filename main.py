from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
import httpx
import os
import json
import uuid
import base64
import secrets
import asyncio
import asyncpg

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
  интеграция на сайт, базовая аналитика.
- Про (популярный) — 49 000 ₽ + 7 900 ₽/мес. Всё из Старта + квиз,
  калькулятор стоимости, обучение на вашем контенте, до 3 000 диалогов,
  ежемесячная доработка.
- Премиум — 89 000 ₽ + 17 900 ₽/мес. Всё из Про + CRM/Битрикс24,
  до 10 000 диалогов, дашборд аналитики, Telegram-бот, приоритетная
  поддержка 24/7.
- Индивидуальный — от 150 000 ₽, состав и помесячная поддержка
  определяются по итогам разбора. Для бизнеса со сложными задачами:
  мультиканальность (сайт + Telegram + WhatsApp), глубокая интеграция
  с CRM и каталогом, несколько агентов под разные задачи, обучение
  команды клиента, выделенная поддержка. Точную цену называть нельзя —
  всегда говорить «от 150 000 ₽, итог после часового разбора».

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

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_lead ON sessions(has_lead) WHERE has_lead = TRUE;
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


# ─────────────────── Metadata extraction ───────────────────

EXTRACTION_SYSTEM = """Ты обрабатываешь диалог посетителя сайта с AI-агентом, который продаёт услугу AI-агентов для бизнеса.

Извлеки структурированные данные. Верни СТРОГО валидный JSON, без markdown, без комментариев, в одну строку или с переносами. Поля:

{
  "business_niche": одна из строк ["дизайн интерьера","салон красоты","юр.услуги","недвижимость","медицина","образование","фитнес","рестораны","ритейл","автоуслуги","строительство","ивенты","IT","другое","не определено"],
  "tariff_interest": одна из ["Старт","Про","Премиум","Индивидуальный","несколько","не определено"],
  "intent_summary": строка 1-2 предложения, что человек спрашивал и чего хочет,
  "has_lead": true ТОЛЬКО если человек явно оставил имя И контакт (телефон или telegram). Если оставил только имя или только сферу — false.,
  "lead_name": имя или null,
  "lead_contact": контакт или null
}"""


async def extract_metadata(session_id: str) -> None:
    """Background: read transcript, ask LLM for structured fields, update sessions row.
    Also fires Telegram notification on first lead detection."""
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
                f"🎯 <b>Новый лид с pervyyii.ru</b>\n\n"
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
    """Receive a lead notification from another family backend and fan out via Telegram.
    Auth: X-Broadcast-Secret header matching BROADCAST_SECRET env."""
    if not BROADCAST_SECRET:
        raise HTTPException(503, "broadcast not configured")
    if not secrets.compare_digest(request.headers.get("x-broadcast-secret", ""), BROADCAST_SECRET):
        raise HTTPException(401, "bad secret")
    payload = await request.json()
    source = payload.get("source") or "—"
    name = payload.get("name") or "—"
    contact = payload.get("contact") or "—"
    niche = payload.get("niche") or "—"
    tariff = payload.get("tariff") or "—"
    summary = payload.get("summary") or ""
    await tg_send(
        f"🎯 <b>Новая заявка с {source}</b>\n\n"
        f"<b>Имя:</b> {name}\n"
        f"<b>Контакт:</b> {contact}\n"
        f"<b>Кто/Сфера:</b> {niche}\n"
        f"<b>Интерес:</b> {tariff}\n\n"
        f"<i>{summary}</i>"
    )
    return {"ok": True}


@app.get("/")
async def root():
    return {"status": "ok", "service": "Pervyyii AI Agent"}


@app.get("/health")
async def health():
    return {"status": "ok", "db": "up" if pool else "down"}


@app.get("/agent.html")
async def agent_page():
    return FileResponse("agent.html")
