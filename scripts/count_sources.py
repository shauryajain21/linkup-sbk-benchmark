import os, json, csv, urllib.request, urllib.error
from urllib.parse import urlparse
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
        return e.code, e.read().decode()[:300]
    except Exception as e:
        return None, str(e)[:300]


def dom(u):
    try:
        return urlparse(u).netloc.replace("www.", "")
    except Exception:
        return u


def claude(q):
    st, resp = post("https://api.anthropic.com/v1/messages",
        {"model": "claude-sonnet-4-6", "max_tokens": 1500, "messages": [{"role": "user", "content": q}],
         "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}]},
        {"x-api-key": os.environ["ANTHROPIC_KEY"], "anthropic-version": "2023-06-01",
         "content-type": "application/json"})
    if st != 200:
        return {"err": str(resp)[:100]}
    cited, retrieved = set(), set()
    for b in resp.get("content", []):
        if b.get("type") == "text":
            for c in b.get("citations", []) or []:
                if c.get("url"):
                    cited.add(c["url"])
        if b.get("type") == "web_search_tool_result":
            for r in (b.get("content") or []):
                if isinstance(r, dict) and r.get("url"):
                    retrieved.add(r["url"])
    urls = cited or retrieved
    return {"cited": len(cited), "retrieved": len(retrieved), "domains": sorted({dom(u) for u in urls})}


def openai(q):
    st, resp = post("https://api.openai.com/v1/responses",
        {"model": "gpt-4o", "tools": [{"type": "web_search"}], "input": q},
        {"Authorization": f"Bearer {os.environ['OPENAI_KEY']}", "content-type": "application/json"})
    if st != 200:
        return {"err": str(resp)[:100]}
    cited = set(); searches = 0
    for it in resp.get("output", []):
        if it.get("type") == "web_search_call":
            searches += 1
        if it.get("type") == "message":
            for c in it.get("content", []):
                for a in (c.get("annotations") or []):
                    if a.get("type") == "url_citation" and a.get("url"):
                        cited.add(a["url"])
    return {"cited": len(cited), "searches": searches, "domains": sorted({dom(u) for u in cited})}


def gemini(q):
    st, resp = post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={os.environ['GEMINI_KEY']}",
        {"contents": [{"parts": [{"text": q}]}], "tools": [{"google_search": {}}]},
        {"content-type": "application/json"})
    if st != 200:
        return {"err": str(resp)[:100]}
    try:
        gm = resp["candidates"][0].get("groundingMetadata", {})
        chunks = gm.get("groundingChunks", []) or []
        titles = [c.get("web", {}).get("title", "") for c in chunks if c.get("web")]
        return {"cited": len(chunks), "queries": len(gm.get("webSearchQueries", []) or []),
                "domains": sorted({t for t in titles if t})[:12]}
    except Exception as e:
        return {"err": "parse " + str(e)[:60]}


APIS = {"claude": claude, "gemini": gemini, "openai": openai}
res = {n: {"row": n} for n, _ in QUERIES}
jobs = []
with ThreadPoolExecutor(max_workers=15) as ex:
    for n, q in QUERIES:
        for name in APIS:
            jobs.append((ex.submit(APIS[name], q), n, name))
    fut2 = {j[0]: (j[1], j[2]) for j in jobs}
    done = 0
    for f in as_completed(fut2):
        n, name = fut2[f]; res[n][name] = f.result(); done += 1
        print(f"[{done}/{len(jobs)}] Q{n:>2} {name:<7} cited={res[n][name].get('cited','?')}")

out = [res[n] for n, _ in QUERIES]
json.dump(out, open(f"{HERE}/results/source_counts.json", "w"), ensure_ascii=False, indent=2)
print("saved")
