# Demo script (3–4 min video)

Covers the three functions (ask, Ship 30 essay, one-pager), how it works, and one trade-off in about 3½ minutes. Timings assume the two waits (essay and one-pager) are cut in editing; on the dev laptop (RTX 3050 4 GB) they take about 3 minutes and 1 minute.

## Before recording (5 min)
1. Run `docker compose up -d`, make sure Ollama is running, and check that http://localhost:8000/api/v1/ready shows `chunks: 16461`.
2. **Warm up:** in a throwaway chat, ask one question so both models load. Answers stay fast for 30 minutes after that.
3. Close the browser tabs you don't need (it frees RAM), set browser zoom to about 125% so text is readable on video, and turn on Do Not Disturb.
4. Open a **New chat** with your display name already set.
5. **Safety net:** generate one essay and one one-pager in a separate chat beforehand. If a live one fails or is slow, you can cut to these.
6. Use the exact prompts below. They are tested and score well above the retrieval threshold. Avoid "running user interviews", which sits right at the cutoff (0.689) and can be refused.

## Script

**0:00–0:20 · The problem (camera)**
> "Lenny's Podcast has almost 300 episodes of great product advice, but finding what a guest actually said, and turning it into something you can share, takes hours. I built an assistant that answers strictly from the transcripts, shows its sources, and writes shareable pieces from them. It runs fully local by default."

**0:20–1:05 · Ask (screen)**
- Point at the badge: *"This runs locally on Ollama, a 4B model, nothing leaves the machine."*
- Type: `What is Naomi Gleit's "understand, identify, and execute" framework?`
- While it streams (first token in about 2 s): *"It searches about 16,000 transcript chunks, then answers only from what it found. Every claim has a numbered citation."*
- Click a source chip, which opens YouTube at the exact timestamp: *"Every source jumps to the moment in the episode."*
- Type: `What's the weather in Paris today?` It refuses instantly: *"If the transcripts don't cover it, it says so instead of making something up."*

**1:05–1:55 · Ship 30 essay**
- Type `finding product-market fit`, then click **Write a Ship 30 essay**.
- *"This uses a Ship 30 for 30 skill: one idea, a strong hook, short paragraphs, a clear takeaway."*
- ✂️ **Cut the wait** (about 3 minutes). Optionally say *"locally this takes about three minutes; I've cut the wait."*
- The essay opens in the side pane. Scroll through the hook, the headings, and the **Sources** list at the end: *"It's grounded in ten passages. During testing I audited the essays and found the model inventing statistics, so I tightened the rules and the invented numbers dropped from fourteen to four."*

**1:55–2:35 · One-pager**
- Type `positioning`, then click **Make a one-pager**.
- ✂️ **Cut the wait** (about 1 minute).
- The HTML one-pager opens. Click **Source**, then **Preview**: *"Generated HTML is untrusted, so it's sanitized on the server and rendered in a sandboxed iframe: no scripts, no network, no forms. That's this note at the bottom."*

**2:35–3:15 · Under the hood and one trade-off (camera, or screen on `eval/results.md`)**
- *"I measured it on a 40-question eval: the right episode was cited 30 out of 30 times, and all 10 out-of-scope questions were refused. Time to first token is 1.9 seconds on a 4 GB laptop GPU, down from 11 seconds."*
- **The trade-off:** *"The biggest decision was model size. A 1.7B model was four times faster, but in my tests it confidently invented the meaning of a well-known framework, and even cited a source for it. For a tool whose whole promise is 'only from the transcripts', I kept the slower 4B model and got the speed back by fixing how the models are loaded instead."*
- Optional, if you have 5 seconds: click the badge: *"Cloud is one click away, but never automatic; sending data off the machine should be the user's choice."*
- Optional, about 10 seconds: in the same menu pick **Local · Agent SDK** and ask a short question: *"The same answer can also run through the Claude Agent SDK, pointed at the local model instead of Anthropic. It's about twice as slow on this laptop, so the direct path is the default."*

**3:15–3:30 · Close (camera)**
> "Everything is in the repo: one `docker compose up`, about twelve minutes from clone to working app, with the PRD, architecture, eval results and the full build log with the coding agent. Thanks for watching."

## Editing notes
- **Cut points:** the two waits (essay, one-pager). Keep a 1-second dissolve so it's obviously a cut, not a trick.
- **If you run long:** drop the badge click in 2:35–3:15 first, then the Source/Preview toggle.
- **If something fails live:** cut to the pre-generated chat from step 5. A Retry on screen is also fine, since it shows the error handling.
