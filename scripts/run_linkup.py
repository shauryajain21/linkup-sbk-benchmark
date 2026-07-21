import os, csv, json, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

API_KEY = os.environ["LINKUP_API_KEY"]
URL = "https://api.linkup.so/v1/search"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

queries = [(int(r["id"]), r["optimized_query_de"])
           for r in csv.DictReader(open(f"{HERE}/data/eval_set.csv"))]


def run(item):
    row, q = item
    payload = json.dumps({
        "q": q,
        "depth": "standard",
        "outputType": "sourcedAnswer",
        "includeInlineCitations": True,
    }).encode()
    req = urllib.request.Request(URL, data=payload, headers={
        "Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
        srcs = data.get("sources", [])
        return {"id": row, "q": q, "answer_de": data.get("answer", ""),
                "sources": [f"{s.get('name','')} | {s.get('url','')}" for s in srcs],
                "n_sources": len(srcs), "ms": int((time.time() - t0) * 1000), "error": None}
    except Exception as e:
        return {"id": row, "q": q, "answer_de": "", "sources": [], "n_sources": 0,
                "ms": int((time.time() - t0) * 1000), "error": str(e)}


results = {}
with ThreadPoolExecutor(max_workers=25) as ex:
    futs = {ex.submit(run, it): it[0] for it in queries}
    for f in as_completed(futs):
        r = f.result(); results[r["id"]] = r
        tag = "ERR" if r["error"] else f'{r["n_sources"]}src {r["ms"]}ms'
        print(f'Q{r["id"]:>2} [{tag}] {r["answer_de"][:60]}')

out = [results[i] for i in sorted(results)]
os.makedirs(f"{HERE}/results", exist_ok=True)
json.dump(out, open(f"{HERE}/results/linkup_standard.json", "w"), ensure_ascii=False, indent=2)
print(f"\n{len(out)} results, errors: {sum(1 for r in out if r['error'])}")
