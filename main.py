from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import httpx
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

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
- Не обсуждай темы вне работы компании."""


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
                    "system": SYSTEM,
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
        return JSONResponse(
            {"error": "empty reply from model", "raw": data},
            status_code=502,
        )
    return JSONResponse({"reply": reply})


@app.get("/")
async def root():
    return {"status": "ok", "service": "Pervyyii AI Agent"}


@app.get("/agent.html")
async def agent_page():
    return FileResponse("agent.html")
