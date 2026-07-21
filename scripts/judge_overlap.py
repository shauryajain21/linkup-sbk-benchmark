import os, json, csv, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
linkup = {int(r["id"]): r for r in csv.DictReader(open(f"{HERE}/data/linkup_standard_answers.csv"))}
api = {r["id"] if "id" in r else r["row"]: r for r in json.load(open(f"{HERE}/results/other_apis_native.json"))}


def clip(s, n=1400):
    return (s or "")[:n]


RUBRIC = (
    "You compare answers from different web-search engines to the SAME German question. "
    "For each pair, classify agreement on the PRIMARY answer (the key fact/number/date/verdict):\n"
    "- MATCH: same bottom-line answer; minor wording/extra-detail differences are fine.\n"
    "- PARTIAL: overlapping topic but differs on a key figure/date/claim, or one is materially vaguer.\n"
    "- DIFF: contradictory, different focus, or one gives no real answer.\n"
    "Return STRICT JSON only."
)


def judge_call(payload_text):
    body = {"model": "gpt-4o", "temperature": 0,
            "messages": [{"role": "system", "content": RUBRIC},
                         {"role": "user", "content": payload_text}],
            "response_format": {"type": "json_object"}}
    req = urllib.request.Request("https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['OPENAI_KEY']}", "content-type": "application/json"})
    last = ""
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read())
            return json.loads(d["choices"][0]["message"]["content"])
        except Exception as e:
            time.sleep(2); last = str(e)[:150]
    return {"error": last}


def do_row(n):
    r = linkup[n]; a = api[n]
    txt = (f"QUESTION:\n{clip(r['optimized_query_de'], 500)}\n\n"
           f"[LINKUP]:\n{clip(r['linkup_answer_de'])}\n\n"
           f"[CLAUDE]:\n{clip(a['claude'])}\n\n"
           f"[GEMINI]:\n{clip(a['gemini'])}\n\n"
           f"[CHATGPT]:\n{clip(a['openai'])}\n\n"
           "Compare each engine to LINKUP, and also the three pairwise combos. "
           'Return JSON with keys exactly: '
           '{"claude_vs_linkup","gemini_vs_linkup","chatgpt_vs_linkup",'
           '"claude_vs_gemini","claude_vs_chatgpt","gemini_vs_chatgpt"} '
           "each one of MATCH/PARTIAL/DIFF.")
    v = judge_call(txt); v["row"] = n
    return v


results = {}
with ThreadPoolExecutor(max_workers=10) as ex:
    futs = {ex.submit(do_row, n): n for n in linkup}
    for f in as_completed(futs):
        v = f.result(); results[v["row"]] = v
        print(f"Q{v['row']:>2}: L~C={v.get('claude_vs_linkup')} "
              f"L~G={v.get('gemini_vs_linkup')} L~X={v.get('chatgpt_vs_linkup')}")

out = [results[n] for n in sorted(results)]
json.dump(out, open(f"{HERE}/results/overlap_verdicts.json", "w"), ensure_ascii=False, indent=2)
print("\nSaved", len(out), "verdicts. errors:", sum(1 for r in out if "error" in r))
