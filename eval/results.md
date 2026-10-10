# Eval results

Run 2026-10-10 10:04 · provider `ollama` · model `qwen3:4b-instruct-2507-q4_K_M` · `python eval/run_eval.py` against the running API. Each question in a fresh session.

## Metrics (PRD §1.2)

| Metric | Target | Result | Pass |
|---|---|---|---|
| M1 gold episode among cited sources (chips) | ≥ 80% | 30/30 (100%) | ✅ |
| M1b gold episode cited with `[n]` in the answer text | (info) | 26/30 (87%) | |
| M2 out-of-scope refused | ≥ 9 of 10 | 10/10 (100%) | ✅ |
| M3 essay 1,125–1,375 words | ≥ 80% of 10 (cloud); local reported | not run |  |
| M4 time to first token, p50 | < 5 s | 11.4 s | ❌ |
| Retrieval latency p50 (request → `citations` event, incl. query embedding) | (info) | 3.5 s | |

M1 is matched by episode slug only: a hit if `gold_episode` is among the cited episodes. The passage-level anchor matching described in `eval_set.json` is not done; it would need episode text and chunk offsets in the schema.

Grounded questions answered (not refused): 27/30 (90%). Errors: none.

## Threshold sweep

Offline replay of `RETRIEVAL_MIN_SCORE` using each question's top retrieval score (from the `done` event). Out-of-scope also counts as refused when a guard or the model refused.

| Threshold | Grounded kept (gold in chips) | Out-of-scope refused |
|---|---|---|
| 0.60 | 30/30 (100%) | 10/10 (100%) |
| 0.63 | 30/30 (100%) | 10/10 (100%) |
| 0.66 | 30/30 (100%) | 10/10 (100%) |
| 0.68 | 30/30 (100%) | 10/10 (100%) |
| 0.69 | 30/30 (100%) | 10/10 (100%) |
| 0.70 | 30/30 (100%) | 10/10 (100%) |
| 0.72 | 28/30 (93%) | 10/10 (100%) |
| 0.75 | 24/30 (80%) | 10/10 (100%) |

## Per question

| id | type | top score | gold rank in chips | refused | TTFT | total |
|---|---|---|---|---|---|---|
| g01 | framework | 0.785 | 1 | no | 8.3 s | 34.8 s |
| g02 | framework | 0.807 | 2 | no | 15.1 s | 29.0 s |
| g03 | framework | 0.793 | 1 | no | 13.8 s | 26.0 s |
| g04 | framework | 0.824 | 1 | no | 11.6 s | 33.8 s |
| g05 | fact | 0.831 | 1 | no | 11.4 s | 32.9 s |
| g06 | attribution | 0.802 | 1 | no | 11.4 s | 29.2 s |
| g07 | framework | 0.741 | 5 | no | 11.4 s | 40.2 s |
| g08 | framework | 0.782 | 1 | no | 11.1 s | 19.6 s |
| g09 | fact | 0.753 | 1 | no | 11.1 s | 21.6 s |
| g10 | fact | 0.722 | 1 | yes | 11.4 s | 12.2 s |
| g11 | fact | 0.785 | 1 | no | 12.3 s | 21.3 s |
| g12 | fact | 0.793 | 1 | no | 11.6 s | 32.7 s |
| g13 | fact | 0.827 | 1 | no | 11.3 s | 18.9 s |
| g14 | framework | 0.821 | 1 | no | 11.0 s | 28.5 s |
| g15 | fact | 0.808 | 1 | no | 11.8 s | 23.1 s |
| g16 | fact | 0.777 | 1 | no | 17.6 s | 31.0 s |
| g17 | framework | 0.709 | 1 | yes | 11.0 s | 11.8 s |
| g18 | framework | 0.744 | 1 | no | 11.2 s | 23.6 s |
| g19 | fact | 0.767 | 1 | no | 10.7 s | 25.3 s |
| g20 | fact | 0.741 | 1 | yes | 11.0 s | 11.7 s |
| g21 | fact | 0.794 | 1 | no | 10.9 s | 27.7 s |
| g22 | fact | 0.704 | 2 | no | 10.6 s | 17.7 s |
| g23 | framework | 0.772 | 1 | no | 10.8 s | 33.0 s |
| g24 | fact | 0.807 | 1 | no | 11.1 s | 24.2 s |
| g25 | fact | 0.838 | 1 | no | 10.4 s | 26.1 s |
| g26 | fact | 0.771 | 1 | no | 11.7 s | 33.0 s |
| g27 | host_question | 0.887 | 1 | no | 11.6 s | 23.0 s |
| g28 | host_question | 0.767 | 1 | no | 11.6 s | 27.5 s |
| g29 | host_question | 0.772 | 1 | no | 12.0 s | 30.9 s |
| g30 | host_question | 0.827 | 1 | no | 11.4 s | 45.5 s |
| o01 | off_topic | 0.631 |  | yes | 3.9 s | 4.0 s |
| o02 | off_topic | 0.660 |  | yes | 0.3 s | 0.3 s |
| o03 | off_topic | 0.567 |  | yes | 0.2 s | 0.2 s |
| o04 | off_topic | 0.590 |  | yes | 0.2 s | 0.2 s |
| o05 | off_topic | 0.672 |  | yes | 0.3 s | 0.3 s |
| o06 | off_topic | 0.630 |  | yes | 0.2 s | 0.2 s |
| o07 | near_domain_trap | 0.725 |  | yes | 8.0 s | 8.7 s |
| o08 | near_domain_trap | 0.742 |  | yes | 12.5 s | 13.2 s |
| o09 | false_attribution_trap | – |  | yes | 0.1 s | 0.1 s |
| o10 | privacy | – |  | yes | 0.0 s | 0.0 s |

## Tuning notes (2026-10-10)

Three full runs (questions only, `--essays 0`), local `qwen3:4b-instruct-2507-q4_K_M` with `OLLAMA_NUM_GPU=16`:

| Run | Change | Answered grounded | M1 | M1b | M2 |
|---|---|---|---|---|---|
| 1 | baseline (2 chunks per episode) | 24/30 | 30/30 | 23/30 | 10/10 |
| 2 | softer `qa` rule 5 (answer what the passages support) | 24/30 | 30/30 | 22/30 | 10/10 |
| 3 | rule 5 reverted; up to 4 chunks per episode | **27/30** | 30/30 | **26/30** | 10/10 |

- **Threshold:** the sweep is flat from 0.60 to 0.70 and grounded questions start dropping at 0.72. `RETRIEVAL_MIN_SCORE` stays at **0.69**: just above the highest off-topic score (0.672), so off-topic questions are refused by retrieval in ~0.3 s; only the two near-domain traps reach the model, which refuses them.
- **Over-refusal was a retrieval problem, not a prompt problem.** In run 1 all six refused grounded questions had the gold episode ranked first, but for five of them the passage containing the answer was not among the five chunks sent to the model (the model was right to refuse). The answer chunks were ranks 3–10 of the 15 candidates, dropped by the 2-per-episode cap because one episode filled 8–15 of the candidates. Softening the prompt (run 2) changed nothing, so it was reverted; raising the cap to 4 (run 3) recovered the three answers predicted (g09, g13, g14).
- **Still refused:** g10 and g20 (answer chunk ranked 10th and 6th, outside the top 5) and g17. Sending more chunks would need a larger context than `num_ctx=8192` leaves room for with essays.
- **M4 (11.4 s p50) misses the < 5 s target locally:** ~3.5 s is retrieval incl. query embedding, the rest is prompt processing on a 4 GB GPU with 16 of 37 layers offloaded. The cloud provider is the path to faster answers.
- **Latency (later the same day):** with Ollama host settings `OLLAMA_KV_CACHE_TYPE=q8_0` and `OLLAMA_MAX_LOADED_MODELS=2` plus `OLLAMA_NUM_GPU=32`, the embedder and chat model stop evicting each other; a 20-question spot check gave the same answers with a full-answer median of 8.5 s (was 30.5 s) and ~1.7 s to first token warm. The M4 numbers above predate this and also include ~2 s per request from `localhost` resolution on Windows (the script now uses `127.0.0.1`); rerun the eval to update M4. See architecture §9.
- **M3** not run yet: 10 local essays take about an hour (`python eval/run_eval.py --essays 10`).
