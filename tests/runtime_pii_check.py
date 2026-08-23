import os, sys, json, asyncio, tempfile

os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
os.environ["DATABASE_URL"] = ""          # без БД — приложение стартует, аналитика off
os.environ["TELEGRAM_POLLING"] = ""
sys.path.insert(0, "/Users/first/Projects/pervyyii-backend")

import httpx

CAPTURED = []          # всё, что уходит наружу
FAKE_ANTHROPIC = {
    "content": [{"type": "text", "text": json.dumps({
        "summary": "Тестовый разбор",
        "problems": [{"title": "Проблема", "detail": "текст"}],
    }, ensure_ascii=False)}],
    "stop_reason": "end_turn",
}

_real_post = httpx.AsyncClient.post
_real_get = httpx.AsyncClient.get

async def fake_post(self, url, **kw):
    CAPTURED.append({"method": "POST", "url": str(url),
                     "json": kw.get("json"), "content": str(kw.get("content"))[:200]})
    req = httpx.Request("POST", str(url))
    if "anthropic" in str(url):
        return httpx.Response(200, json=FAKE_ANTHROPIC, request=req)
    return httpx.Response(200, json={"ok": True, "result": {}}, request=req)

async def fake_get(self, url, **kw):
    CAPTURED.append({"method": "GET", "url": str(url)})
    req = httpx.Request("GET", str(url))
    # страница «клиента» с ПД в тексте
    html = """<html><head><title>Прайм Тент — аренда шатров</title>
    <meta name="description" content="Шатры в Москве"></head><body>
    <h1>Аренда шатров</h1><h2>Услуги</h2>
    <p>Менеджер Иван Петров, тел. +7 916 555-33-11, почта ivan.petrov@primetent.ru</p>
    <p>Офис: ул. Профсоюзная, д. 125. Карта 4276 3800 1234 5678</p>
    <form><input name="phone"></form><p>Мы предоставляем шатры и тенты в аренду для свадеб, корпоративных мероприятий и выставок по всей Московской области. В наличии конструкции от 50 до 500 квадратных метров, прозрачные и白 белые, с подогревом и без. Монтаж занимает от четырёх часов, работаем без выходных, выезд замерщика бесплатный. Собственный склад в Москве, более двухсот комплектов на площадке, доставка по области входит в стоимость при заказе от трёх суток аренды. Гарантия на конструкции, страхование мероприятия, круглосуточная поддержка на площадке в день события.</p><p>Мы предоставляем шатры и тенты в аренду для свадеб, корпоративных мероприятий и выставок по всей Московской области. В наличии конструкции от 50 до 500 квадратных метров, прозрачные и白 белые, с подогревом и без. Монтаж занимает от четырёх часов, работаем без выходных, выезд замерщика бесплатный. Собственный склад в Москве, более двухсот комплектов на площадке, доставка по области входит в стоимость при заказе от трёх суток аренды. Гарантия на конструкции, страхование мероприятия, круглосуточная поддержка на площадке в день события.</p></body></html>"""
    return httpx.Response(200, text=html, request=req)

httpx.AsyncClient.post = fake_post
httpx.AsyncClient.get = fake_get

import main
async def _always_public(host):
    return True
main._host_is_public = _always_public
PAGE_HTML = """<html><head><title>Прайм Тент — аренда шатров</title>
<meta name="description" content="Шатры в Москве"></head><body>
<h1>Аренда шатров</h1><h2>Наши услуги</h2>
<p>Менеджер Иван Петров, тел. +7 916 555-33-11, почта ivan.petrov@primetent.ru</p>
<p>Офис: ул. Профсоюзная, д. 125. Карта 4276 3800 1234 5678</p>
<form><input name="phone"></form><p>Мы предоставляем шатры и тенты в аренду для свадеб, корпоративных мероприятий и выставок по всей Московской области. В наличии конструкции от 50 до 500 квадратных метров, прозрачные и白 белые, с подогревом и без. Монтаж занимает от четырёх часов, работаем без выходных, выезд замерщика бесплатный. Собственный склад в Москве, более двухсот комплектов на площадке, доставка по области входит в стоимость при заказе от трёх суток аренды. Гарантия на конструкции, страхование мероприятия, круглосуточная поддержка на площадке в день события.</p><p>Мы предоставляем шатры и тенты в аренду для свадеб, корпоративных мероприятий и выставок по всей Московской области. В наличии конструкции от 50 до 500 квадратных метров, прозрачные и白 белые, с подогревом и без. Монтаж занимает от четырёх часов, работаем без выходных, выезд замерщика бесплатный. Собственный склад в Москве, более двухсот комплектов на площадке, доставка по области входит в стоимость при заказе от трёх суток аренды. Гарантия на конструкции, страхование мероприятия, круглосуточная поддержка на площадке в день события.</p></body></html>"""
async def _fake_safe_fetch(url, verify, headers, max_redirects=5):
    return httpx.Response(200, text=PAGE_HTML, request=httpx.Request("GET", url))
main._safe_fetch = _fake_safe_fetch
from fastapi.testclient import TestClient

SECRETS = {
    "phone": "+7 916 555-33-11",
    "phone_digits": "9165553311",
    "email": "ivan.petrov@primetent.ru",
    "address": "Профсоюзная",
    "card": "4276 3800 1234 5678",
    "name_after_phrase": "Сергей",
    "url_query_phone": "79991112233",
}

with TestClient(main.app) as client:
    print("--- сценарий 1: /chat с ПД ---")
    r = client.post("/chat", json={
        "messages": [{"role": "user", "content":
            f"Здравствуйте, меня зовут {SECRETS['name_after_phrase']}. "
            f"Телефон {SECRETS['phone']}, почта {SECRETS['email']}. "
            f"Живу ул. {SECRETS['address']}, д. 125. Карта {SECRETS['card']}."}],
        "session_id": "runtime-test-1",
    })
    print("  status:", r.status_code)

    print("--- сценарий 2: /audit со страницей, где ПД в тексте и в query ---")
    r = client.post("/audit", json={
        "url": f"https://primetent-example.ru/lp?phone={SECRETS['url_query_phone']}&utm=vk"})
    print("  status:", r.status_code)

out = [c for c in CAPTURED if "anthropic" in c["url"]]
print(f"\n=== запросов к Anthropic перехвачено: {len(out)} ===")
dump = json.dumps(out, ensure_ascii=False)
# Каталог берём из окружения: путь к scratchpad конкретной сессии живёт недолго,
# а захардкоженный превращал тест в падающий у всех, кроме одного запуска.
dump_path = os.path.join(os.environ.get("PII_DUMP_DIR") or tempfile.gettempdir(),
                         "anthropic_dump.json")
with open(dump_path, "w") as f:
    f.write(json.dumps(out, ensure_ascii=False, indent=1))
print(f"  дамп исходящего: {dump_path}")

print("\n=== ПОИСК ПД В ИСХОДЯЩЕМ JSON ===")
bad = 0
for label, val in SECRETS.items():
    hit = val in dump
    if hit: bad += 1
    print(f"  {'УТЕЧКА' if hit else 'чисто '}  {label}: {val}")
print("\n=== ключи/токены ===")
print("  ключ в теле:", "УТЕЧКА" if "test-key-not-real" in dump else "чисто (ключ только в headers)")
print(f"\nВЕРДИКТ: {'NO-GO, утечек ' + str(bad) if bad else 'GO — контрольные значения не найдены'}")
# Ненулевой код возврата: без него провалившийся тест выглядел как успешный прогон.
sys.exit(1 if bad else 0)
