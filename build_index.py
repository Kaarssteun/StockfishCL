"""Builds a metadata index of all finished Fishtest runs from the public API.
Polite: one request at a time with a delay; resumable (progress in state.json).
Output: fishtest_index.csv (one row per run, newest first as fetched; deduplicated by id).
Usage: python build_index.py [--delay 0.6] [--last-page N]"""
import argparse, csv, json, math, os, sys, time, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--delay", type=float, default=0.6)
ap.add_argument("--last-page", type=int, default=0)
args = ap.parse_args()

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "fishtest_index.csv")
STATE = os.path.join(HERE, "state.json")
URL = "https://tests.stockfishchess.org/api/finished_runs?page={}"
UA = "fishtest-index/1.0 (personal research; contact via github.com/Kaarssteun)"

FIELDS = ["id", "start_time", "last_updated", "username", "branch", "base", "tests_repo",
          "resolved_new", "resolved_base", "info", "tc", "new_tc", "threads", "book",
          "type", "elo0", "elo1", "elo_model", "result", "llr", "games", "wins", "losses",
          "draws", "ptnml", "elo", "elo_err95", "crashes", "time_losses", "num_games",
          "spsa_params", "approver", "is_green", "is_yellow", "failed", "deleted",
          "new_signature", "base_signature", "new_options", "base_options", "link"]


def elo_est(r):
    p = r.get("pentanomial")
    if p and sum(p) > 0:
        sc, n = [0, 0.25, 0.5, 0.75, 1], sum(p)
        m = sum(s * c for s, c in zip(sc, p)) / n
        var = sum(c * (s - m) ** 2 for s, c in zip(sc, p)) / n
    else:
        w, l, d = r.get("wins", 0), r.get("losses", 0), r.get("draws", 0)
        n = w + l + d
        if n == 0:
            return "", ""
        m = (w + 0.5 * d) / n
        var = (w * (1 - m) ** 2 + l * m ** 2 + d * (0.5 - m) ** 2) / n
    if not 0 < m < 1 or n < 2:
        return "", ""
    f = lambda x: -400 * math.log10(1 / x - 1)
    se = math.sqrt(var / n)
    lo, hi = f(max(1e-6, m - 1.96 * se)), f(min(1 - 1e-6, m + 1.96 * se))
    return round(f(m), 2), round((hi - lo) / 2, 2)


def row(k, v):
    a, r = v.get("args", {}), v.get("results", {})
    s = a.get("sprt") or {}
    sp = a.get("spsa")
    typ = "spsa" if sp else ("sprt" if s else "games")
    if typ == "sprt":
        res = s.get("state") or ("stopped" if v.get("finished") else "")
    elif typ == "spsa":
        res = "spsa"
    else:
        res = "fixed_games"
    if v.get("failed"):
        res = (res + ";failed").strip(";")
    elo, err = elo_est(r)
    w, l, d = r.get("wins", 0), r.get("losses", 0), r.get("draws", 0)
    return {
        "id": k, "start_time": str(v.get("start_time", ""))[:19], "last_updated": str(v.get("last_updated", ""))[:19],
        "username": a.get("username", ""), "branch": a.get("new_tag", ""), "base": a.get("base_tag", ""),
        "tests_repo": a.get("tests_repo", ""), "resolved_new": a.get("resolved_new", ""),
        "resolved_base": a.get("resolved_base", ""), "info": " ".join(str(a.get("info", "")).split()),
        "tc": a.get("tc", ""), "new_tc": a.get("new_tc", ""), "threads": a.get("threads", ""), "book": a.get("book", ""),
        "type": typ, "elo0": s.get("elo0", ""), "elo1": s.get("elo1", ""), "elo_model": s.get("elo_model", ""),
        "result": res, "llr": round(s["llr"], 3) if "llr" in s else "", "games": w + l + d, "wins": w, "losses": l,
        "draws": d, "ptnml": " ".join(map(str, r["pentanomial"])) if r.get("pentanomial") else "",
        "elo": elo, "elo_err95": err, "crashes": r.get("crashes", ""), "time_losses": r.get("time_losses", ""),
        "num_games": a.get("num_games", ""), "spsa_params": len(sp.get("params", [])) if sp else "",
        "approver": v.get("approver", ""), "is_green": v.get("is_green", ""), "is_yellow": v.get("is_yellow", ""),
        "failed": v.get("failed", ""), "deleted": v.get("deleted", ""),
        "new_signature": a.get("new_signature", ""), "base_signature": a.get("base_signature", ""),
        "new_options": a.get("new_options", ""), "base_options": a.get("base_options", ""),
        "link": f"https://tests.stockfishchess.org/tests/view/{k}",
    }


def fetch(page):
    for attempt in range(6):
        try:
            req = urllib.request.Request(URL.format(page), headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            wait = 5 * 2 ** attempt
            print(f"page {page}: {e}; retry in {wait}s", flush=True)
            time.sleep(wait)
    raise SystemExit(f"giving up on page {page}")


state = json.load(open(STATE)) if os.path.exists(STATE) else {"next_page": 1, "rows": 0}
seen = set()
if os.path.exists(CSV) and state["next_page"] > 1:
    with open(CSV, encoding="utf-8", newline="") as fh:
        seen = {r["id"] for r in csv.DictReader(fh)}
new_file = not os.path.exists(CSV) or state["next_page"] == 1
out = open(CSV, "w" if new_file else "a", encoding="utf-8", newline="")
wr = csv.DictWriter(out, fieldnames=FIELDS)
if new_file:
    wr.writeheader()

page, t0 = state["next_page"], time.time()
while True:
    if args.last_page and page > args.last_page:
        break
    data = fetch(page)
    if not data:
        print(f"page {page} empty: done", flush=True)
        break
    items = data.items() if isinstance(data, dict) else ((x["_id"], x) for x in data)
    for k, v in items:
        if k in seen:
            continue
        seen.add(k)
        wr.writerow(row(k, v))
        state["rows"] += 1
    out.flush()
    page += 1
    state["next_page"] = page
    json.dump(state, open(STATE, "w"))
    if page % 50 == 0:
        el = time.time() - t0
        print(f"page {page}, rows {state['rows']}, {el/60:.1f} min", flush=True)
    time.sleep(args.delay)
out.close()
state["done"] = True
json.dump(state, open(STATE, "w"))
print(f"done: {state['rows']} rows", flush=True)
