"""Run eval/eval_set.json through the running API and write eval/results.md (PRD §1.2, M1–M4).

Usage: python eval/run_eval.py [--essays N] [--base-url URL]
Standard library only, so it runs on the host. Each question gets a fresh session.
"""

import argparse
import datetime as dt
import json
import re
import statistics
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).parent
REFUSAL = re.compile(r"transcripts don't cover this|was not a guest|can't help with personal", re.I)
CITE = re.compile(r"\[(\d+)\]")
ESSAY_TOPICS = [
    "finding product-market fit",
    "retention",
    "pricing",
    "hiring product managers",
    "growth loops",
    "user onboarding",
    "positioning",
    "managing up",
    "building a growth team",
    "running user interviews",
]
THRESHOLDS = [0.60, 0.63, 0.66, 0.68, 0.69, 0.70, 0.72, 0.75]
MIN_WORDS, MAX_WORDS = 1125, 1375


@dataclass
class Run:
    text: str = ""
    citations: list[dict] = field(default_factory=list)
    artifact: dict | None = None
    done: dict | None = None
    error: dict | None = None
    t_citations: float | None = None
    ttft: float | None = None
    total: float = 0.0


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/") + "/api/v1"

    def call(self, method: str, path: str, body: dict | None = None, timeout: float = 30) -> urllib.request.addinfourl:
        req = urllib.request.Request(
            self.base + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"content-type": "application/json"},
        )
        return urllib.request.urlopen(req, timeout=timeout)

    def json(self, method: str, path: str, body: dict | None = None) -> dict:
        with self.call(method, path, body) as res:
            return json.load(res)

    def ask(self, content: str, hint: str | None = None) -> Run:
        session = self.json("POST", "/sessions", {"user_meta": {"display_name": "eval"}})
        run, start = Run(), time.perf_counter()
        with self.call("POST", f"/sessions/{session['id']}/messages", {"content": content, "route_hint": hint}, timeout=1800) as res:
            buffer = ""
            for raw in res:
                buffer += raw.decode()
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    self.handle(run, block, time.perf_counter() - start)
        run.total = time.perf_counter() - start
        if run.artifact:
            run.artifact = self.json("GET", f"/artifacts/{run.artifact['id']}?session_id={session['id']}")
        return run

    @staticmethod
    def handle(run: Run, block: str, elapsed: float) -> None:
        event = data = ""
        for line in block.split("\n"):
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: "):
                data += line[6:]
        payload = json.loads(data) if data else None
        if event == "citations":
            run.citations, run.t_citations = payload, elapsed
        elif event == "token":
            run.ttft = run.ttft if run.ttft is not None else elapsed
            run.text += payload["text"]
        elif event == "artifact":
            run.artifact = payload
        elif event == "done":
            run.done = payload
        elif event == "error":
            run.error = payload


def refused(run: Run) -> bool:
    return not run.citations or bool(REFUSAL.search(run.text))


def cited_slugs(run: Run) -> set[str]:
    return {run.citations[int(n) - 1]["slug"] for n in CITE.findall(run.text) if 0 < int(n) <= len(run.citations)}


def top_score(run: Run) -> float | None:
    return (run.done or {}).get("retrieval_top_score")


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "n/a"


def p50(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def secs(v: float | None) -> str:
    return f"{v:.1f} s" if v is not None else "–"


def run_questions(api: Api, items: list[dict]) -> list[tuple[dict, Run]]:
    results = []
    for i, item in enumerate(items, 1):
        run = api.ask(item["question"])
        results.append((item, run))
        status = "ERROR " + run.error["code"] if run.error else ("refused" if refused(run) else "answered")
        print(f"[{i}/{len(items)}] {item['id']} {status} top={top_score(run)} {run.total:.0f}s", flush=True)
    return results


def run_essays(api: Api, n: int) -> list[tuple[str, Run, int | None]]:
    results = []
    for topic in ESSAY_TOPICS[:n]:
        run = api.ask(f"Write a Ship 30 essay on {topic}", "essay")
        match = re.search(r"\(([\d,]+) words\)", run.text)
        words = int(match.group(1).replace(",", "")) if match else None
        results.append((topic, run, words))
        print(f"essay '{topic}': {words} words, {run.total:.0f}s {run.error['code'] if run.error else ''}", flush=True)
    return results


def threshold_sweep(results: list[tuple[dict, Run]]) -> list[str]:
    """Replays the threshold rule offline: a question is refused by retrieval if its top score is below t."""
    rows = ["| Threshold | Grounded kept (gold in chips) | Out-of-scope refused |", "|---|---|---|"]
    grounded = [(i, r) for i, r in results if i["kind"] == "grounded"]
    oos = [(i, r) for i, r in results if i["kind"] == "out_of_scope"]
    for t in THRESHOLDS:
        kept = sum(1 for i, r in grounded if (top_score(r) or 0) >= t and i["gold_episode"] in {c["slug"] for c in r.citations})
        ref = sum(1 for _, r in oos if top_score(r) is None or top_score(r) < t or refused(r))
        rows.append(f"| {t:.2f} | {pct(kept, len(grounded))} | {pct(ref, len(oos))} |")
    return rows


def report(config: dict, results: list[tuple[dict, Run]], essays: list[tuple[str, Run, int | None]]) -> str:
    grounded = [(i, r) for i, r in results if i["kind"] == "grounded"]
    oos = [(i, r) for i, r in results if i["kind"] == "out_of_scope"]
    m1 = sum(1 for i, r in grounded if i["gold_episode"] in {c["slug"] for c in r.citations})
    m1_text = sum(1 for i, r in grounded if i["gold_episode"] in cited_slugs(r))
    m2 = sum(1 for _, r in oos if refused(r))
    answered = [r for _, r in grounded if not refused(r) and not r.error]
    ttfts = [r.ttft for _, r in results if r.ttft is not None and r.citations and not r.error]
    retrievals = [r.t_citations for _, r in results if r.t_citations is not None]
    in_range = [w for _, _, w in essays if w is not None and MIN_WORDS <= w <= MAX_WORDS]
    errors = [(i["id"], r.error["code"]) for i, r in results if r.error]
    m4 = p50(ttfts)
    lines = [
        "# Eval results",
        "",
        f"Run {dt.datetime.now():%Y-%m-%d %H:%M} · provider `{config['active']['provider']}` · model `{config['active']['model']}` · "
        f"`python eval/run_eval.py` against the running API. Each question in a fresh session.",
        "",
        "## Metrics (PRD §1.2)",
        "",
        "| Metric | Target | Result | Pass |",
        "|---|---|---|---|",
        f"| M1 gold episode among cited sources (chips) | ≥ 80% | {pct(m1, len(grounded))} | {'✅' if m1 >= 0.8 * len(grounded) else '❌'} |",
        f"| M1b gold episode cited with `[n]` in the answer text | (info) | {pct(m1_text, len(grounded))} | |",
        f"| M2 out-of-scope refused | ≥ 9 of 10 | {pct(m2, len(oos))} | {'✅' if m2 >= 0.9 * len(oos) else '❌'} |",
        f"| M3 essay 1,125–1,375 words | ≥ 80% of 10 (cloud); local reported | {pct(len(in_range), len(essays)) if essays else 'not run'} | "
        f"{('✅' if len(in_range) >= 0.8 * len(essays) else '❌') if essays else ''} |",
        f"| M4 time to first token, p50 | < 5 s | {secs(m4)} | {'✅' if m4 is not None and m4 < 5 else '❌'} |",
        f"| Retrieval latency p50 (request → `citations` event, incl. query embedding) | (info) | {secs(p50(retrievals))} | |",
        "",
        "M1 is matched by episode slug only: a hit if `gold_episode` is among the cited episodes. The passage-level "
        "anchor matching described in `eval_set.json` is not done; it would need episode text and chunk offsets in the schema.",
        "",
        f"Grounded questions answered (not refused): {pct(len(answered), len(grounded))}. Errors: {errors or 'none'}.",
        "",
        "## Threshold sweep",
        "",
        "Offline replay of `RETRIEVAL_MIN_SCORE` using each question's top retrieval score (from the `done` event). "
        "Out-of-scope also counts as refused when a guard or the model refused.",
        "",
        *threshold_sweep(results),
        "",
        "## Per question",
        "",
        "| id | type | top score | gold rank in chips | refused | TTFT | total |",
        "|---|---|---|---|---|---|---|",
    ]
    for item, r in results:
        slugs = [c["slug"] for c in r.citations]
        gold = item.get("gold_episode")
        rank = (str(slugs.index(gold) + 1) if gold in slugs else "–") if gold else ""
        score = top_score(r)
        lines.append(
            f"| {item['id']} | {item['type']} | {f'{score:.3f}' if score is not None else '–'} | {rank} | "
            f"{'yes' if refused(r) else 'no'}{' (error ' + r.error['code'] + ')' if r.error else ''} | {secs(r.ttft)} | {secs(r.total)} |"
        )
    if essays:
        lines += ["", "## Essays", "", "| topic | words | in range | total |", "|---|---|---|---|"]
        for topic, r, words in essays:
            ok = words is not None and MIN_WORDS <= words <= MAX_WORDS
            lines.append(f"| {topic} | {words if words is not None else 'error'} | {'yes' if ok else 'no'} | {secs(r.total)} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")  # localhost costs ~2 s per request on Windows (IPv6 first)
    parser.add_argument("--essays", type=int, default=10, help="essay runs for M3 (0 to skip; ~5 min each locally)")
    parser.add_argument("--out", type=Path, default=HERE / "results.md")
    args = parser.parse_args()
    api = Api(args.base_url)
    config = api.json("GET", "/config")
    items = json.loads((HERE / "eval_set.json").read_text(encoding="utf-8"))["items"]
    results = run_questions(api, items)
    essays = run_essays(api, args.essays)
    args.out.write_text(report(config, results, essays), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
