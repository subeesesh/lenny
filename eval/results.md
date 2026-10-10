# Eval results

Run 2026-10-10 11:55 · provider `ollama` · model `qwen3:4b-instruct-2507-q4_K_M` · `python eval/run_eval.py` against the running API. Each question in a fresh session.

## Metrics (PRD §1.2)

| Metric | Target | Result | Pass |
|---|---|---|---|
| M1 gold episode among cited sources (chips) | ≥ 80% | 30/30 (100%) | ✅ |
| M1b gold episode cited with `[n]` in the answer text | (info) | 27/30 (90%) | |
| M2 out-of-scope refused | ≥ 9 of 10 | 10/10 (100%) | ✅ |
| M3 essay 1,125–1,375 words | ≥ 80% of 10 (cloud); local reported | 4/10 (40%) | ❌ |
| M4 time to first token, p50 | < 5 s | 1.9 s | ✅ |
| Retrieval latency p50 (request → `citations` event, incl. query embedding) | (info) | 0.2 s | |

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
| g01 | framework | 0.785 | 1 | no | 2.4 s | 9.0 s |
| g02 | framework | 0.807 | 2 | no | 2.0 s | 5.8 s |
| g03 | framework | 0.793 | 1 | no | 1.8 s | 5.4 s |
| g04 | framework | 0.824 | 1 | no | 1.8 s | 8.4 s |
| g05 | fact | 0.831 | 1 | no | 1.8 s | 8.3 s |
| g06 | attribution | 0.802 | 1 | no | 1.9 s | 5.5 s |
| g07 | framework | 0.741 | 5 | no | 2.0 s | 7.8 s |
| g08 | framework | 0.782 | 1 | no | 1.8 s | 9.7 s |
| g09 | fact | 0.753 | 1 | no | 1.8 s | 5.3 s |
| g10 | fact | 0.722 | 1 | yes | 2.0 s | 2.3 s |
| g11 | fact | 0.785 | 1 | no | 2.4 s | 4.9 s |
| g12 | fact | 0.793 | 1 | no | 1.9 s | 6.8 s |
| g13 | fact | 0.827 | 1 | no | 1.8 s | 4.3 s |
| g14 | framework | 0.821 | 1 | no | 1.8 s | 6.7 s |
| g15 | fact | 0.808 | 1 | no | 2.0 s | 6.2 s |
| g16 | fact | 0.777 | 1 | no | 1.8 s | 6.4 s |
| g17 | framework | 0.709 | 1 | yes | 1.9 s | 2.2 s |
| g18 | framework | 0.744 | 1 | no | 1.9 s | 5.6 s |
| g19 | fact | 0.767 | 1 | no | 1.7 s | 5.7 s |
| g20 | fact | 0.741 | 1 | yes | 2.1 s | 2.4 s |
| g21 | fact | 0.794 | 1 | no | 2.0 s | 6.1 s |
| g22 | fact | 0.704 | 2 | no | 1.9 s | 4.7 s |
| g23 | framework | 0.772 | 1 | no | 2.0 s | 9.2 s |
| g24 | fact | 0.807 | 1 | no | 2.1 s | 10.7 s |
| g25 | fact | 0.838 | 1 | no | 2.0 s | 8.6 s |
| g26 | fact | 0.771 | 1 | no | 2.4 s | 8.0 s |
| g27 | host_question | 0.887 | 1 | no | 2.0 s | 7.4 s |
| g28 | host_question | 0.767 | 1 | no | 2.1 s | 7.0 s |
| g29 | host_question | 0.772 | 1 | no | 1.8 s | 7.4 s |
| g30 | host_question | 0.827 | 1 | no | 1.8 s | 8.6 s |
| o01 | off_topic | 0.631 |  | yes | 0.2 s | 0.2 s |
| o02 | off_topic | 0.660 |  | yes | 0.2 s | 0.2 s |
| o03 | off_topic | 0.567 |  | yes | 0.2 s | 0.2 s |
| o04 | off_topic | 0.590 |  | yes | 0.2 s | 0.2 s |
| o05 | off_topic | 0.672 |  | yes | 0.2 s | 0.2 s |
| o06 | off_topic | 0.630 |  | yes | 0.2 s | 0.2 s |
| o07 | near_domain_trap | 0.725 |  | yes | 2.1 s | 2.3 s |
| o08 | near_domain_trap | 0.742 |  | yes | 1.9 s | 2.1 s |
| o09 | false_attribution_trap | – |  | yes | 0.0 s | 0.0 s |
| o10 | privacy | – |  | yes | 0.0 s | 0.0 s |

## Essays

| topic | words | in range | total |
|---|---|---|---|
| finding product-market fit | 1269 | yes | 141.9 s |
| retention | 1086 | no | 104.1 s |
| pricing | 1327 | yes | 155.7 s |
| hiring product managers | 1290 | yes | 127.9 s |
| growth loops | 1408 | no | 150.3 s |
| user onboarding | 1435 | no | 141.3 s |
| positioning | 1375 | yes | 159.2 s |
| managing up | 1396 | no | 144.7 s |
| building a growth team | 1110 | no | 111.7 s |
| running user interviews | error | no | 0.2 s |

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
- **Latency (later the same day):** with Ollama host settings `OLLAMA_KV_CACHE_TYPE=q8_0` and `OLLAMA_MAX_LOADED_MODELS=2` plus `OLLAMA_NUM_GPU=32`, the embedder and chat model stop evicting each other; a 20-question spot check gave the same answers with a full-answer median of 8.5 s (was 30.5 s) and ~1.7 s to first token warm. The M4 numbers in runs 1–3 predated this and also include ~2 s per request from `localhost` resolution on Windows (the script now uses `127.0.0.1`); rerun the eval to update M4. See architecture §9.
- **M3:** see "Notes on this run" below.

## Notes on this run (2026-10-10 11:55)

- Settings: Ollama host `OLLAMA_KV_CACHE_TYPE=q8_0`, `OLLAMA_MAX_LOADED_MODELS=2`; `OLLAMA_NUM_GPU=32`; up to 4 chunks per episode; essays with 5 passages and the word-delta retry. M4 (1.9 s) now meets the target; it was 11.4 s before the latency tuning.
- **M3, local: 4/10.** First drafts were 616–1,044 words, so every essay used the one retry; finals missed by up to 60 words either way (1,086, 1,110, 1,396, 1,408, 1,435). The PRD's ≥ 80% target is for the cloud provider; the 4B model is imprecise about word counts and the PRD allows only one retry. The 10th topic ("running user interviews") was refused by retrieval at 0.689, just under the 0.69 threshold (short topics score lower than full questions).
- This run predates the essay accuracy changes below (10 passages, stricter grounding rules), which also make essays longer.

## Accuracy audit (2026-10-10)

Every number and quoted phrase in the generated text was checked against the passages the model was given.

- **Q&A (27 answers from this run):** 18/18 numbers appear in the sources. A few close paraphrases were shown in quotation marks; `qa/SKILL.md` now says to quote only word-for-word text.
- **Essays (9 from this run, 5 passages):** 17/50 numbers were not in the sources, and some were invented case studies presented as fact ("in one case, a company saw a 2.5x increase in activation…").
- **Fix:** essays now retrieve 10 passages (Q&A stays at 5) and `ship30/SKILL.md` forbids invented case studies, companies, statistics and dialogue, requires every number to come from the passages, and limits non-sourced examples to clearly marked "Imagine…" hypotheticals. Worst case with 10 passages is ~6,900 of the 8,192-token context (retry included).
- **Re-test on the four worst topics** (onboarding, managing up, pricing, positioning): numbers not in the sources fell from 14 to 4 (one of them "4x", a restatement of "2 to 4 times"), and invented case studies disappeared. Remaining non-verbatim quotes are unattributed writing devices (example customer lines such as "I'll think about it.", example questions, quoted terms); none puts invented words in a guest's mouth. Essays now take ~3–3.5 min locally and run 1,309–1,547 words.
