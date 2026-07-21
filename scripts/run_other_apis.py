import os, json, csv, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUERIES = [(int(r["id"]), r["optimized_query_de"])
           for r in csv.DictReader(open(f"{HERE}/data/eval_set.csv"))]


def post(url, data, headers, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]
    except Exception as e:
        return None, str(e)[:400]


def claude(q):
    st, resp = post("https://api.anthropic.com/v1/messages",
        {"model": "claude-sonnet-4-6", "max_tokens": 1500,
         "messages": [{"role": "user", "content": q}],
         "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}]},
        {"x-api-key": os.environ["ANTHROPIC_KEY"], "anthropic-version": "2023-06-01",
         "content-type": "application/json"})
    if st == 200:
        return "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text").strip()
    return f"__ERR__ {st} {str(resp)[:150]}"


def openai(q):
    st, resp = post("https://api.openai.com/v1/responses",
        {"model": "gpt-4o", "tools": [{"type": "web_search"}], "input": q},
        {"Authorization": f"Bearer {os.environ['OPENAI_KEY']}", "content-type": "application/json"})
    if st == 200:
        txt = ""
        for it in resp.get("output", []):
            if it.get("type") == "message":
                for c in it.get("content", []):
                    if c.get("type") == "output_text":
                        txt += c.get("text", "")
        return txt.strip()
    return f"__ERR__ {st} {str(resp)[:150]}"


def gemini(q):
    st, resp = post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={os.environ['GEMINI_KEY']}",
        {"contents": [{"parts": [{"text": q}]}], "tools": [{"google_search": {}}]},
        {"content-type": "application/json"})
    if st == 200:
        try:
            return "".join(p.get("text", "") for p in resp["candidates"][0]["content"]["parts"] if "text" in p).strip()
        except Exception as e:
            return f"__ERR__ parse {str(e)[:80]}"
    return f"__ERR__ {st} {str(resp)[:150]}"


APIS = {"claude": claude, "gemini": gemini, "openai": openai}
results = {n: {"row": n} for n, _ in QUERIES}


def task(n, q, name):
    t0 = time.time()
    return n, name, APIS[name](q), int((time.time() - t0) * 1000)


jobs = []
with ThreadPoolExecutor(max_workers=15) as ex:
    for n, q in QUERIES:
        for name in APIS:
            jobs.append(ex.submit(task, n, q, name))
    done = 0
    for f in as_completed(jobs):
        n, name, ans, ms = f.result()
        results[n][name] = ans
        done += 1
        tag = "ERR" if ans.startswith("__ERR__") else f"{len(ans)}c"
        print(f"[{done}/{len(jobs)}] Q{n:>2} {name:<7} {tag} {ms}ms")

out = [results[n] for n, _ in QUERIES]
json.dump(out, open(f"{HERE}/results/other_apis_native.json", "w"), ensure_ascii=False, indent=2)
errs = {name: sum(1 for r in out if r.get(name, "").startswith("__ERR__")) for name in APIS}
print("\nSaved 41 rows. Errors:", errs)
