import os, sys, json, re, asyncio

os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
os.environ["DATABASE_URL"] = ""
os.environ["TELEGRAM_POLLING"] = ""
os.environ["PT_LEAD_GOAL_ENABLED"] = "1"
sys.path.insert(0, "/Users/first/Projects/pervyyii-backend")

import httpx

RAW_PHONE = "+7 916 001-34-34"
RAW_DIGITS = "79160013434"
OUTBOUND = []

CHAT_REPLY = {
    "content": [{"type": "text", "text": "Ориентировочно 5,2 млн рублей. Чтобы подготовить точный расчёт — подскажите ваше имя и телефон (или почту)?"}],
    "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1},
}
EXTRACT_REPLY = {
    "content": [{"type": "text", "text": json.dumps({
        "construction_type": "ангар", "size_city": "12х30, Москва",
        "intent_summary": "Тестовый разбор"}, ensure_ascii=False)}],
    "stop_reason": "end_turn",
}

async def fake_post(self, url, **kw):
    OUTBOUND.append({"url": str(url), "json": kw.get("json")})
    req = httpx.Request("POST", str(url))
    body = kw.get("json") or {}
    if "anthropic" in str(url):
        fake = EXTRACT_REPLY if body.get("max_tokens") == 400 else CHAT_REPLY
        return httpx.Response(200, json=fake, request=req)
    return httpx.Response(200, json={"ok": True, "result": {}}, request=req)

httpx.AsyncClient.post = fake_post

import main
from fastapi.testclient import TestClient


class FakeConn:
    def __init__(self, state): self.s = state
    async def execute(self, sql, *args):
        self.s["writes"].append((sql, args))
        if "consent_at=COALESCE(consent_at, NOW())" in sql:
            self.s["consent_at"] = "given"
    async def fetch(self, sql, *args):
        if "FROM messages" in sql: return self.s.get("messages_rows", [])
        return []
    async def fetchrow(self, sql, *args):
        if "FROM sessions" in sql: return self.s.get("session_row")
        return None
    async def fetchval(self, sql, *args):
        if "SELECT consent_at" in sql: return self.s["consent_at"]
        if "lead_goal_sent = TRUE" in sql: return args[0]
        return None

class FakeAcquire:
    def __init__(self, conn): self.conn = conn
    async def __aenter__(self): return self.conn
    async def __aexit__(self, *a): return False

class FakePool:
    def __init__(self, conn): self.conn = conn
    def acquire(self): return FakeAcquire(self.conn)


def fresh_state(**kw):
    s = {"writes": [], "consent_at": None}
    s.update(kw)
    main.pool = FakePool(FakeConn(s))
    return s

def digits(x): return re.sub(r"\D", "", str(x))

def db_has_raw(state):
    return any(RAW_DIGITS in digits(args) for _, args in state["writes"])

def outbound_has_raw():
    return any(RAW_DIGITS in digits(o) for o in OUTBOUND)

client = TestClient(main.app)
ok = 0

# A. Контакт до согласия: заглушка, редакция, ни одного полного номера нигде
state = fresh_state()
OUTBOUND.clear()
r = client.post("/chat", json={"client": "prime-tent", "session_id": "t-a",
    "messages": [{"role": "user", "content": f"Ангар 12х30, перезвоните {RAW_PHONE}"}]}).json()
assert r.get("consent_required") is True, r
assert r["reply"] == main._CONSENT_REQUIRED_REPLY
assert not db_has_raw(state), "полный номер попал в запись БД"
assert not outbound_has_raw(), "полный номер ушёл во внешний запрос"
assert not any("anthropic" in o["url"] for o in OUTBOUND), "LLM вызван до согласия при контакте"
assert any("INSERT INTO messages" in sql and args and "[PHONE" in str(args) for sql, args in state["writes"]), \
    "маскированное сообщение не записано"
assert any("'consent_shown'" in sql for sql, _ in state["writes"]), "нет события consent_shown"
assert any("contact_before_consent=TRUE" in sql for sql, _ in state["writes"]), "нет флага contact_before_consent"
assert not any("lead_goal_sent = TRUE" in sql for sql, _ in state["writes"]), "лид-цель тронута без согласия"
assert "lead" not in r
ok += 1; print("A ok: контакт до согласия маскирован, лида нет, LLM не вызван")

# B. Согласие клеймом в /chat: полный поток, лид, наружу всё равно только маска
state = fresh_state()
OUTBOUND.clear()
r = client.post("/chat", json={"client": "prime-tent", "session_id": "t-b",
    "consent_policy": "2026-08-01",
    "messages": [{"role": "user", "content": f"Меня зовут Тест, перезвоните {RAW_PHONE}"}]}).json()
assert state["consent_at"] == "given", "клейм согласия не записан"
assert r.get("lead") is True, r
assert any("INSERT INTO messages" in sql and RAW_DIGITS in digits(args) for sql, args in state["writes"]), \
    "с согласием полное сообщение должно сохраниться"
assert any("anthropic" in o["url"] for o in OUTBOUND)
assert not outbound_has_raw(), "в Anthropic ушёл сырой номер (152-ФЗ маскирование)"
ok += 1; print("B ok: с согласием — полный поток, лид есть, за рубеж только маска")

# C. Без согласия и без контакта: ответ просит контакт -> show_consent + событие
state = fresh_state()
OUTBOUND.clear()
r = client.post("/chat", json={"client": "prime-tent", "session_id": "t-c",
    "messages": [{"role": "user", "content": "Сколько стоит ангар 12 на 30?"}]}).json()
assert r.get("show_consent") is True, r
assert "подскажите" in r["reply"].lower()
assert any("'consent_shown'" in sql for sql, _ in state["writes"])
ok += 1; print("C ok: просьба контакта в ответе -> show_consent")

# D. Backstop extract_metadata: сырой контакт в истории, согласия нет -> ни лида, ни уведомлений
state = fresh_state(
    messages_rows=[{"role": "user", "content": f"Перезвоните {RAW_PHONE}"}],
    session_row={"has_lead": False, "lead_notified": False, "referrer": "prime-tent.ru/",
                 "interest": None, "consent_at": None})
calls = []
async def rec_alert(*a, **k): calls.append(("alert", a))
async def rec_email(*a, **k): calls.append(("email", a)); return True
async def rec_offline(*a, **k): calls.append(("offline", a))
main.alerts_send, main.send_lead_email, main.send_offline_conversion = rec_alert, rec_email, rec_offline
asyncio.run(main.extract_metadata("t-d", "prime-tent"))
assert not calls, f"уведомления ушли без согласия: {calls}"
upd = [args for sql, args in state["writes"] if "UPDATE sessions SET" in sql and "business_niche" in sql]
assert upd and upd[0][4] is False and upd[0][6] is None, "lead/contact записаны без согласия"
ok += 1; print("D ok: backstop в extract_metadata — уведомлений нет, контакт не сохранён")

# E. /widget-events consent_given -> согласие зафиксировано на сессии
state = fresh_state()
r = client.post("/widget-events", json={"client": "prime-tent", "event": "consent_given",
    "session_id": "t-e", "page": "https://prime-tent.ru/vozduhoopornye/",
    "policy_version": "2026-08-01"}).json()
assert r == {"ok": True}
assert state["consent_at"] == "given", "consent_given не записал согласие в сессию"
ok += 1; print("E ok: событие consent_given фиксирует согласие и версию политики")

print(f"\nВсе проверки пройдены: {ok}/5")
