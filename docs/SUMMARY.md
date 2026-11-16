# One-page summary (English)

**Luis Gabriel Albrecht** · portfolio project · the company and all data are **fictional**
(Tapiri Pagamentos, a card-machine provider for small merchants). The code, docs and UI are in
Brazilian Portuguese; this page is the English overview.

## What it is

An AI customer-support system in two parts:

1. **Ticket triage.** Reads a customer message, masks personal data before anything leaves the
   server, classifies it with Claude (or Gemini) into category, priority and sentiment, and
   routes it to the right queue. If the AI fails, a rule-based fallback takes over.
2. **Merchant support agent.** Answers merchants using 30 help articles and the merchant's own
   account data (sales, payouts, card machines), shows the source, and hands off to a human when
   needed (urgency, fraud, manipulation attempts, no source in the knowledge base).

A 21-second video with real recorded AI answers: [`docs/video/demonstracao.webm`](video/demonstracao.webm).

## Results (with 95% confidence intervals)

| | Measured | 95% range |
|---|---|---|
| Triage: all 4 fields right on the same ticket | 36/40 | 77% to 96% |
| Triage: urgent tickets released without a human | 0 | — |
| Agent: resolved without a human **and correct** (held-out test 2) | 11/21 | 32% to 72% |
| Agent: resolved without a human **and wrong** (held-out test 2) | 2/40 | 1% to 17% |
| Agent: resolved without a human **and correct** (held-out test 3, harder) | 11/23 | 29% to 67% |
| Agent: resolved without a human **and wrong** (held-out test 3, harder) | 5/40 | 5% to 26% |
| Urgent cases and manipulation attempts sent to a human | 8/8 | 68% to 100% |
| Test personal data sent to the AI | 0 of 6 | — |
| Cost per agent message | US$ 0.00091 | — |

**How to read this.** These are small, synthetic test sets, so the ranges are wide and real
traffic would likely score lower. "Correct" is judged by an LLM (Claude Sonnet 5.5) against a
written rubric; a kit to measure judge–human agreement (Cohen's kappa) is ready, not yet run.

## Method

- **Train/test separation.** Changes were decided on 60 development questions only. Held-out
  test sets were opened once, with the code frozen, run 3 times, and nothing was tuned after.
- **A third test set** was written by a separate agent that only saw the company description,
  with topic and writing style randomly drawn (terse chat, long story, transcribed audio,
  elderly user, typos), so it would not resemble the first two. It was harder: correct answers
  held steady, but wrong-without-human rose from 2/40 to 5/40. Three of those were cases flagged
  as borderline before the run; the rest were small extrapolations the answer check missed.
  Urgent cases, manipulation attempts and personal data stayed perfect in all 3 runs.
- **Negative results are kept.** A citation-based answer check (the model rewrites the answer
  citing exact source passages; code drops any uncited sentence) looked promising. Measured on
  the 60, it was worse: correct-without-human fell from 23/35 to 17/35 and wrong-without-human
  rose from 2/60 to 5/60. When forced to cite, the model copied source fragments instead of
  answering. It stays off, with the full write-up.

## Design decisions

- **The merchant comes from the session, never from the text.** Tools take no merchant
  parameter, so the model cannot choose whose data it reads.
- **No source, no advice.** Every instruction must cite an article returned by the search.
- **The code does the math.** Dates, business days and net amounts are computed in code; the
  model only writes.
- **Model self-confidence never decides alone.** Objective reasons and the answer check do.
- **Personal data is masked first:** CPF/CNPJ (check digits), cards (Luhn), phones, e-mail, and,
  by context rules, ID numbers, street addresses and names.
- **Conversation history is untrusted input.** It is masked, scanned for injection, and passed to
  the model as data, never as instructions; a forged "agent said the fee is 0%" turn did not fool
  it in a live test.
- **Human review queue** (`/fila`): what the team receives when the AI hands off.

## Engineering

Python 3.12 · FastAPI · Claude API (strict tool use, prompt caching) · Gemini embeddings with a
BM25 fallback · PostgreSQL/SQLite · Docker · GitHub Actions · 600+ tests with fake AI clients
(no paid calls), Playwright browser tests (mobile width, contrast, keyboard), and a retrieval
regression gate that runs in CI with stored embeddings.

## Where to look

- [`README.md`](../README.md) (Portuguese): how to run, routes, every decision.
- [`docs/ATENDIMENTO.md`](ATENDIMENTO.md) (Portuguese): each stage, run and error, with dates.
- [`avaliacao/resultados/`](../avaliacao/resultados/): every evaluation report.
