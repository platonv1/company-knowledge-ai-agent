# Jarvis — Company Knowledge Assistant

[![CI](https://github.com/platonv1/company-knowledge-ai-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/platonv1/company-knowledge-ai-agent/actions/workflows/ci.yml)

A grounded RAG assistant over a company's controlled documents. It answers from the
knowledge base, cites the document and page behind every claim, and says so when the
documents don't cover a question.

The demo corpus is a fictional financial institution, **Jarvis Financial Group**.

```
You: How many annual leave days do employees get?

Jarvis: Full-time employees are entitled to 15 days of paid annual leave per
        calendar year, accruing at one and a quarter days per calendar month. [S2]

        Where this comes from
        S2  Annual Leave Policy
            Leave_Policy_v2.pdf · page 1 · 2. Annual Leave Entitlement · version 2.0
```

That answer is the whole point of the project. The corpus contains **two** leave policies:
an archived 2025 one saying 12 days and an active 2026 one saying 15. On raw similarity the
**archived** policy scores *higher* (0.352 vs 0.327 on this corpus), because its text is shorter and less
diluted. A pipeline without an active-version filter answers "12 days" and cites a real
document and a real page — a wrong answer that looks perfectly sourced. That case is pinned
by a test ([`test_document_service.py`](tests/integration/test_document_service.py)).

---

## Run it

Nothing here needs an API key. The repository ships offline providers for both embeddings
and generation, so you can clone it and see the whole pipeline work.

```bash
docker compose up -d                       # Postgres 16 + pgvector on :5433
uv venv --python python3.12 .venv          # or: python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env

.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.generate_corpus          # 13 PDFs into documents/
EMBEDDING_PROVIDER=hashing RELEVANCE_FLOOR=0.20 \
  .venv/bin/python -m scripts.ingest_documents documents/ --reset

EMBEDDING_PROVIDER=hashing RELEVANCE_FLOOR=0.20 LLM_PROVIDER=extractive \
  .venv/bin/uvicorn app.main:app --port 8000
```

Open <http://localhost:8000>.

For step-by-step setup, loading your own documents, and putting Jarvis on an existing
website, see **[INSTRUCTION.md](INSTRUCTION.md)**.

Set `ADMIN_API_KEY` in `.env` before using the document endpoints — they fail closed with
503 while it is still the placeholder, rather than leaving document management open.

**With real models**, put an OpenAI key in `.env` and drop the overrides — `LLM_PROVIDER` and
`EMBEDDING_PROVIDER` default to `openai`, and `RELEVANCE_FLOOR` to 0.35.

### The offline providers

| Provider | What it is | Why it exists |
|---|---|---|
| `EMBEDDING_PROVIDER=hashing` | Feature-hashed bag of words, L2-normalised | Runs with no key; retrieval tests exercise real similarity ordering rather than stubbed scores |
| `LLM_PROVIDER=extractive` | Sentence selection from the retrieved context | Runs with no key; gives the eval a non-LLM baseline — "the model scores X" means little without "sentence selection alone scores Y" |

Both are materially worse than real models — the hashing embedder has no sense of paraphrase,
and the extractive answerer cannot aggregate across sources. That gap is the measurement, so
it isn't dressed up.

---

## How it works

```
Browser (vanilla JS, served by FastAPI)
  │  POST /api/chat
  ▼
FastAPI ── CORS allowlist · per-IP token bucket · Pydantic validation
  ▼
ChatService
  ├─ 1. Rewrite follow-up into a standalone question   (skipped on turn 1)
  ├─ 2. Embed                                          [swappable]
  ├─ 3. pgvector cosine search, over-fetch search_k=8
  │     filters: org_id, doc_status='active'
  ├─ 4. Relevance gate: absolute floor + relative drop-off
  │     ── nothing clears it → refuse, WITHOUT calling the LLM
  ├─ 5. Build <source id="S1" …> context blocks
  ├─ 6. Generate                                       [swappable]
  └─ 7. Resolve [Sn] markers → citations; drop invented markers
  ▼
{ answer, sources[], conversation_id, grounded }
```

### Five decisions worth explaining

**The LLM is never called on a retrieval miss.** If nothing clears the relevance gate,
`ChatService` returns the refusal directly. Fabrication is prevented structurally on the most
dangerous path, rather than by asking a model nicely.

**The model never writes a page number.** It emits opaque markers (`[S1]`); the backend maps
markers to documents and pages. A marker that wasn't supplied is stripped from the answer and
logged. A plausible-but-wrong page number is indistinguishable from a right one to a reader,
so the model is never given the opportunity to produce one.

**Follow-ups are rewritten before retrieval.** Embedding `"How many days?"` retrieves noise.
A history-aware rewrite runs first, and is skipped on the first turn to save a round trip.
Conversation history is used *only* for that rewrite — it is never passed to the answering
model as evidence, so stale conversation content can't override the knowledge base.

**Tables are read with `extract_tables()`, not from page text.** A wrapped table cell doesn't
extract in reading order: `pdfplumber` emits "Core banking" and "unavailable" either side of
the next column. Table regions are excluded from the body text and rebuilt as Markdown, which
also stops the same rows being embedded twice.

**Scanned documents fail loudly.** A PDF with no text layer would otherwise index zero-length
chunks and report success — Jarvis would then claim to know nothing about a handbook it was
given. `Scanned_Notice.pdf` exists in the corpus to keep that path honest.

---

## Evaluation

RAG quality is invisible without measurement, so the eval harness is part of the build rather
than a follow-up task. It is also the instrument used to tune the relevance floor and chunk
size.

```bash
python -m scripts.run_eval              # retrieval metrics
python -m scripts.run_eval --sweep      # calibrate the threshold
python -m scripts.run_eval --with-answers   # also generate and judge answers (needs a key)
```

The golden set is **72 cases**, generated alongside the corpus: 56 facts, 11 deliberately
unanswerable questions, and 5 multi-turn follow-ups. Expected page numbers are resolved by
searching the *rendered* PDFs for each fact's anchor text, so no page number in the golden set
is hand-typed and it cannot drift from the documents.

### Measured baseline

`EMBEDDING_PROVIDER=hashing`, `LLM_PROVIDER=extractive`, floor 0.20, top_k 5, 75 chunks,
72 golden cases:

| Metric | Result |
|---|---|
| Page hit@5 | 70.5% (43/61) |
| Document hit@5 | 72.1% (44/61) |
| Over-refusal | 13.1% (8/61) |
| Refusal accuracy, gate only | 27.3% (3/11) |
| **Refusal accuracy, end to end** | **81.8% (9/11)** |
| **Citations resolvable** | **72/72** |
| Faithfulness (LLM-as-judge) | needs an API key — the offline provider cannot judge |
| **Version leaks** | **0** |
| Follow-ups, evaluated without rewriting | **0/5** |

Four of those are worth reading closely.

**Refusal happens in two stages.** The gate stops 27.3% of unanswerable questions on its own;
end to end the system refuses 81.8% of them, because the answerer refuses when the retrieved
passages don't contain an answer. That gap is why the gate is tuned to favour recall rather
than to do all the refusing itself.

**Citations resolvable is 72/72.** Every citation that reached output mapped to a chunk that
was actually supplied — no invented reference survived, across the whole golden set.

**Version leaks are zero at every threshold**, so the active-version filter holds independently
of tuning.

**Follow-ups score 0/5 on their raw text.** That is the measurement that justifies the
query-rewriting step, rather than an assertion that it was needed.

These are offline-provider numbers, and a floor rather than a quality claim. The hashing
embedder has no notion of paraphrase and the extractive answerer picks sentences by word
overlap, so a real model should beat this substantially — re-running with a key is the first
thing to do.

### Calibrating the floor

`CLAUDE.md` §26 suggests `SIMILARITY_THRESHOLD=0.70`. The sweep shows what that does:

| floor | page hit@5 | refusal accuracy (gate) | over-refusal |
|---|---|---|---|
| 0.15 | 72.1% | 0.0% | 8.2% |
| **0.20** | **70.5%** | **27.3%** | **13.1%** |
| 0.25 | 57.4% | 81.8% | 26.2% |
| 0.30 | 31.1% | 100% | 59.0% |
| 0.35 | 14.8% | 100% | 77.0% |
| **0.70** | **0.0%** | 100% | **100%** |

At 0.70, Jarvis refuses every single question. Cosine scores aren't comparable across
embedding models, so the floor has to be calibrated per provider against the golden set —
measured, not guessed. Refusal accuracy is read alongside over-refusal, because refusing
everything maximises it.

The sweep retrieves candidates once and re-applies the gate in memory for each combination,
so calibration is cheap enough to actually repeat.

---

## Layout

```
app/
  api/           chat · documents · health · deps
  core/          config · database · logging · security · rate_limit
  rag/           extraction · cleaning · chunking · tokenizer
                 embeddings · retriever · context_builder · citations · metadata
  llm/           base · openai_provider · extractive · prompts
  models/        db (SQLAlchemy) · chat · documents (Pydantic)
  services/      chat_service · document_service
  repositories/  vector_store · conversation_repository
frontend/chat/   index.html · styles.css · app.js   (no build step)
eval/            corpus_facts.yaml (the golden set) · results/
scripts/         generate_corpus · ingest_documents · run_eval · corpus_*
alembic/         one migration: tenant-ready schema + HNSW index
```

A `Dockerfile` builds a ~110 MB image that runs as an unprivileged user and reports
container health from `/api/health`; `docker compose --profile app up` runs it next to the
database. CI runs lint, the full suite against pgvector, and the image build on every push.

`org_id` is in the schema from the first migration even though one organization exists today —
retrofitting tenant isolation is a rewrite, adding a column now is free. `doc_status` is
denormalised onto `chunks` so the active-version filter hits an index without a join; the cost
is that archiving must propagate, which `set_document_status` does in one transaction.

## Tests

```bash
.venv/bin/python -m pytest        # 194 tests
```

Unit tests make no network calls and use fakes for all three provider interfaces. Integration
tests run against the Docker Postgres, in a **separate `jarvis_test` database** — the fixtures
truncate tables, so pointing them at the dev database would wipe an ingested corpus on every
run. The suite applies the real migrations once per session, so the migration chain is covered
too.

## API

| Endpoint | Auth | |
|---|---|---|
| `POST /api/chat` | origin allowlist + rate limit | `{message, conversation_id?}` → `{answer, sources[], conversation_id, grounded}` |
| `GET /api/health` | none | database, indexed counts, provider configuration |
| `POST /api/documents` | `X-Admin-Key` | PDF upload; validated by magic bytes, not extension |
| `GET /api/documents` | `X-Admin-Key` | list with ingestion status and any error |
| `DELETE /api/documents/{id}` | `X-Admin-Key` | |
| `POST /api/documents/{id}/archive` | `X-Admin-Key` | removes from retrieval, keeps the audit trail |

`/api/chat` is unauthenticated by design — it is a public website widget — so it sits behind a
CORS origin allowlist and a per-IP token bucket. Without those it is an open proxy to a paid
model. The limiter is in-process, which is correct for one instance and wrong behind a load
balancer; that needs Redis before scaling out.

## Not built

Deferred deliberately, with nothing in the architecture blocking them: hybrid search (BM25 +
vector, measurable against the existing harness), reranking, an admin console, the embeddable
iframe widget, role-based retrieval, live multi-tenancy, OCR, and cloud deployment.
