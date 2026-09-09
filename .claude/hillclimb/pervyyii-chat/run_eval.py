#!/usr/bin/env python3
"""Прогон эвала агента pervyyii через живой /api/hub/chat.

Зовём реальную точку входа, а не пересобираем вызов Anthropic: эвал должен
мерить то, что видит клиент, вместе с промптом, постобработкой и лимитами.
"""
import argparse
import asyncio
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path

import httpx

FLOW_DIR = Path(__file__).resolve().parent
ENDPOINT = "https://pervyyii.ru/api/hub/chat"
# Метка в User-Agent: по ней прогоны эвала отличаются от живых диалогов в БД.
USER_AGENT = "pervyyii-eval/1.0 (+internal quality check)"

MD_MARKERS = ["**", "##", "__"]
BULLET_RE = re.compile(r"^\s*[-*•+]\s+", re.M)
AI_LATIN_RE = re.compile(r"\bAI[\s-]?(?=[а-яё])", re.I)


def norm(s: str) -> str:
    return s.replace(" ", " ").replace(" ", " ").replace(" ", " ")


def squeeze_digits(s: str) -> str:
    return re.sub(r"(?<=\d)\s(?=\d)", "", norm(s))


def contains(haystack: str, needle: str) -> bool:
    h, n = norm(haystack).lower(), norm(needle).lower()
    if n in h:
        return True
    return squeeze_digits(needle).lower() in squeeze_digits(haystack).lower()


def grade(case: dict, reply: str) -> tuple[dict, dict]:
    facts_missing = []
    for group in case.get("must_include_any", []):
        if not any(contains(reply, v) for v in group):
            facts_missing.append(" | ".join(group))

    invented = [v for v in case.get("must_not_include", []) if contains(reply, v)]

    fmt_problems = [m for m in MD_MARKERS if m in reply]
    if BULLET_RE.search(reply):
        fmt_problems.append("буллет в начале строки")
    if AI_LATIN_RE.search(reply):
        fmt_problems.append("AI латиницей перед кириллицей")

    grades = {
        "facts": 0.0 if facts_missing else 1.0,
        "no_invention": 0.0 if invented else 1.0,
        "format": 0.0 if fmt_problems else 1.0,
    }
    why = {
        "facts": ("не назвал: " + "; ".join(facts_missing)) if facts_missing else "все обязательные факты на месте",
        "no_invention": ("выдумал: " + "; ".join(invented)) if invented else "запрещённых утверждений нет",
        "format": ("; ".join(fmt_problems)) if fmt_problems else "формат чистый",
    }
    return grades, why


async def run_case(client: httpx.AsyncClient, case: dict, rep: int, args, sem) -> dict:
    async with sem:
        started = time.monotonic()
        attempts = 0
        last_err = None
        for attempt in range(4):
            attempts = attempt + 1
            if time.monotonic() - started > args.timeout_s:
                last_err = "wall-clock ceiling"
                break
            try:
                r = await client.post(
                    ENDPOINT,
                    json={"client": "pervyyii", "messages": [{"role": "user", "content": case["prompt"]}]},
                    headers={"content-type": "application/json", "user-agent": USER_AGENT},
                    timeout=args.timeout_s,
                )
                if r.status_code == 429 or r.status_code >= 500:
                    last_err = f"HTTP {r.status_code}"
                    await asyncio.sleep(min(30, 2 ** attempt) + random.uniform(0, 2))
                    continue
                data = r.json()
                if "error" in data:
                    last_err = f"upstream: {data['error']}"
                    break
                reply = (data.get("reply") or "").strip()
                if not reply:
                    last_err = "пустой ответ"
                    break
                served = data.get("model")
                if args.expect_model and served and served != args.expect_model:
                    # Подменённая модель делает сравнение бессмысленным — валим громко.
                    last_err = f"ответила модель {served}, ждали {args.expect_model}"
                    break
                grades, why = grade(case, reply)
                usage = data.get("usage") or {}
                return {
                    "ok": True,
                    "row": {
                        "prompt_id": case["id"],
                        "rep": rep,
                        "prompt": case["prompt"],
                        "tags": case.get("tags", []),
                        "response": reply,
                        "status": "ok",
                        "stop_reason": data.get("stop_reason"),
                        "model": data.get("model"),
                        "grade": grades,
                        "explanation": why,
                        "latency_s": round(time.monotonic() - started, 2),
                        "attempts": attempts,
                        "usage": {
                            "input_tokens": usage.get("input_tokens", 0),
                            "output_tokens": usage.get("output_tokens", 0),
                            "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
                            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
                        },
                        "meta": {"session_id": data.get("session_id"), "note": case.get("note", "")},
                    },
                }
            except (httpx.HTTPError, json.JSONDecodeError) as e:
                last_err = f"{type(e).__name__}: {e}"
                await asyncio.sleep(min(30, 2 ** attempt) + random.uniform(0, 2))
        return {
            "ok": False,
            "err": {
                "prompt_id": case["id"],
                "rep": rep,
                "failure_class": "timeout" if last_err == "wall-clock ceiling" else "harness_or_serving_error",
                "detail": last_err,
                "attempts": attempts,
            },
        }


def harness_sha() -> str:
    h = hashlib.sha256()
    for p in (Path(__file__), FLOW_DIR / "cases.json"):
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="baseline")
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--timeout-s", type=float, default=90.0)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="прогнать только первые N кейсов (пилот)")
    ap.add_argument("--expect-model", default="claude-sonnet-5",
                    help="модель, которая должна обслужить запрос; несовпадение валит кейс")
    ap.add_argument("--approve-harness", action="store_true")
    args = ap.parse_args()

    state_path = FLOW_DIR / "_state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    sha = harness_sha()
    if state.get("harness_sha") not in (None, sha) and not args.approve_harness:
        print(f"Раннер или кейсы изменились (sha {state.get('harness_sha')} -> {sha}).")
        print("Проверь diff и перезапусти с --approve-harness.")
        return 2
    if args.approve_harness or "harness_sha" not in state:
        state["harness_sha"] = sha
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    cases = json.loads((FLOW_DIR / "cases.json").read_text())
    if args.limit:
        cases = cases[: args.limit]

    out_dir = FLOW_DIR / args.variant
    (out_dir / "traces").mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.jsonl"
    errors_path = out_dir / "errors.jsonl"

    done = set()
    if results_path.exists():
        for line in results_path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                done.add((row["prompt_id"], row.get("rep", 0)))

    todo = [(c, r) for c in cases for r in range(args.reps) if (c["id"], r) not in done]
    if not todo:
        print("Всё уже прогнано, нечего делать.")
        return 0

    print(f"Прогоняю {len(todo)} вызовов ({len(cases)} кейсов x {args.reps} реп), вариант {args.variant}")
    sem = asyncio.Semaphore(args.concurrency)
    started = time.monotonic()
    async with httpx.AsyncClient() as client:
        tasks = [run_case(client, c, r, args, sem) for c, r in todo]
        for coro in asyncio.as_completed(tasks):
            res = await coro
            if res["ok"]:
                row = res["row"]
                with results_path.open("a") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                trace = [
                    {"role": "user", "content": row["prompt"]},
                    {"role": "assistant", "content": row["response"]},
                ]
                (out_dir / "traces" / f"{row['prompt_id']}_rep{row['rep']}.json").write_text(
                    json.dumps(trace, ensure_ascii=False, indent=2)
                )
                mark = "OK " if all(v == 1.0 for v in row["grade"].values()) else "ФЕЙЛ"
                print(f"  {mark} {row['prompt_id']}")
            else:
                with errors_path.open("a") as f:
                    f.write(json.dumps(res["err"], ensure_ascii=False) + "\n")
                print(f"  ОШИБКА {res['err']['prompt_id']}: {res['err']['detail']}")

    rows = [json.loads(l) for l in results_path.read_text().splitlines() if l.strip()]
    n = len(rows)
    print(f"\nПрогон занял {time.monotonic() - started:.0f} с. Кейсов с результатом: {n}")
    for metric in ("facts", "no_invention", "format"):
        passed = sum(1 for r in rows if r["grade"].get(metric) == 1.0)
        share = passed / n if n else 0
        ci = 1.96 * ((share * (1 - share) / n) ** 0.5) if n else 0
        print(f"  {metric:<13} {passed}/{n} = {share:.0%}  ±{ci:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
