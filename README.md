# SBK search evaluation — reproduction & findings

A transparent, reproducible re-run of the 41-question German
health-insurance evaluation, shared so we can review the results together.
Every query, answer, and score in this repo can be regenerated with the
scripts provided.

## What we ran

- **Queries:** the same 41 questions, formulated with the guidance in Linkup's
  [`linkup-for-agents`](https://github.com/LinkupPlatform/linkup-for-agents)
  repo (role framing, explicit identifiers, numbered sub-questions, explicit
  dates). The identical query text was sent to every engine.
- **Linkup:** `sourcedAnswer`, `depth: standard`, inline citations on.
- **Reference engines:** Claude, Gemini, and ChatGPT with their native
  web-search tools enabled, default settings.

> `sourcedAnswer` is an LLM synthesis of the underlying search results, returned
> with the sources it was grounded on. The raw search results carry the same
> information.

## Findings

| Measure | Result |
|---|---|
| Simple-lookup queries — correct on the primary answer | **35 / 36** |
| &nbsp;&nbsp;of which fully verified against an independent source | 31 / 36 |
| &nbsp;&nbsp;core-correct with a minor secondary caveat | 4 / 36 |
| Open-ended questions | **5 / 5 complete and sufficient** |
| Independent cross-check: all three reference engines at least partially agree with Linkup | **34 / 41 (83%)** |
| Average sources cited per Linkup answer | **~30** |

Every verdict above is itemised, with its verification basis and source, in
[`data/linkup_grading.csv`](data/linkup_grading.csv). The few caveats concern
fast-moving, real-time values (e.g. a next-day forecast) or recent regulatory
timelines, where sources can legitimately differ between runs. We would welcome
aligning on the grading approach for these cases.

### Cross-engine agreement

An independent LLM judge (`gpt-4o`, no web access) compared each engine's answer
to Linkup's on the primary fact:

| vs. Linkup | Match | Partial | Different |
|---|---|---|---|
| Claude  | 26 | 11 | 4 |
| Gemini  | 25 | 13 | 3 |
| ChatGPT | 23 | 11 | 7 |

### Source coverage

| Engine | Avg. sources cited | Linkup cites more by |
|---|---|---|
| Linkup (standard) | 29.9 | — |
| Gemini | 15.0 | +99% (≈2×) |
| Claude | 5.8 | +416% (≈5.2×) |
| ChatGPT | 3.9 | +667% (≈7.7×) |

Compared with the average of the three reference engines (8.2), Linkup cites
about **+263% (≈3.6×) more sources**.

## Contents

```
data/
  eval_set.csv                 the 41 questions (English gloss + German query)
  linkup_standard_answers.csv  Linkup answers, sources, latency
  linkup_grading.csv           per-question verdict + verification basis & source
  other_apis_native.json       Claude / Gemini / ChatGPT answers (verbatim)
  source_counts.csv            sources cited per engine, per question
  overlap_verdicts.csv         per-question agreement vs Linkup
scripts/
  run_linkup.py  run_other_apis.py  count_sources.py  judge_overlap.py
```

## Reproduce

```bash
export LINKUP_API_KEY=...
export ANTHROPIC_KEY=... OPENAI_KEY=... GEMINI_KEY=...

python scripts/run_linkup.py
python scripts/run_other_apis.py
python scripts/count_sources.py
python scripts/judge_overlap.py
```

No third-party packages are required (Python standard library only).
