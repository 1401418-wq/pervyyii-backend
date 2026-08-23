import os, sys, json, asyncio

os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
os.environ["DATABASE_URL"] = ""
os.environ["TELEGRAM_POLLING"] = ""
os.environ["PT_OFFLINE_CONV_ENABLED"] = "1"
os.environ["METRIKA_OAUTH_TOKEN"] = "test-token-not-real"
sys.path.insert(0, "/Users/first/Projects/pervyyii-backend")

import httpx
import main

UPLOADINGS = {
    "YCLID": [
        {"id": 1001, "status": "PROCESSED", "linked_quantity": 1},
        {"id": 1002, "status": "LINKAGE_FAILURE", "linked_quantity": None},
        {"id": 1003, "status": "UPLOADED", "linked_quantity": None},
    ],
    "CLIENT_ID": [
        {"id": 1004, "status": "PROCESSED", "linked_quantity": None},
    ],
}

ROWS = [
    {"session_id": "s-linked", "offline_conv_uploading_id": "1001"},
    {"session_id": "s-failed", "offline_conv_uploading_id": "1002"},
    {"session_id": "s-inflight", "offline_conv_uploading_id": "1003"},
    {"session_id": "s-counting", "offline_conv_uploading_id": "1004"},
    {"session_id": "s-unknown", "offline_conv_uploading_id": "9999"},
]

UPDATES = []
NOTIFIES = []


async def fake_get(self, url, **kw):
    id_type = (kw.get("params") or {}).get("client_id_type")
    body = {"uploadings": UPLOADINGS.get(id_type, [])}
    return httpx.Response(200, json=body, request=httpx.Request("GET", str(url)))


class FakeConn:
    async def fetch(self, q, *a):
        return ROWS if "offline_conv_uploading_id IS NOT NULL" in q else []

    async def execute(self, q, *a):
        UPDATES.append((a[0], a[1]) if len(a) > 1 else (q, a))
        return "UPDATE 1"


class FakeAcquire:
    async def __aenter__(self):
        return FakeConn()

    async def __aexit__(self, *a):
        return False


class FakePool:
    def acquire(self):
        return FakeAcquire()


async def fake_notify(text):
    NOTIFIES.append(text)
    return True


async def main_test():
    httpx.AsyncClient.get = fake_get
    main.pool = FakePool()
    main._lead_notify = fake_notify

    await main._offline_conv_verify_linkage()

    by_session = dict(UPDATES)
    print("обновления состояний:", json.dumps(by_session, ensure_ascii=False))
    print("уведомлений отправлено:", len(NOTIFIES))

    ok = True

    def check(name, cond):
        nonlocal ok
        print(("  OK   " if cond else "  ПРОВАЛ ") + name)
        ok = ok and cond

    check("привязанная загрузка остаётся sent", by_session.get("s-linked") == "sent")
    check("LINKAGE_FAILURE переводится в unlinked", by_session.get("s-failed") == "unlinked")
    check("ещё не обработанную не трогаем", "s-inflight" not in by_session)
    check("PROCESSED без счётчика привязок не трогаем", "s-counting" not in by_session)
    check("незнакомую загрузку не трогаем", "s-unknown" not in by_session)
    check("алерт ровно один (только на unlinked)", len(NOTIFIES) == 1)
    check("алерт помечен как технический", NOTIFIES and NOTIFIES[0].startswith("Техническое."))
    check("алерт не ушёл клиентским каналом", all("Прайм-Тент" in n for n in NOTIFIES))

    print("\nИТОГ:", "всё сошлось" if ok else "ЕСТЬ ПРОВАЛЫ")
    return 0 if ok else 1


sys.exit(asyncio.run(main_test()))
