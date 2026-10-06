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
.venv/bin/python -m scripts.ingest_documents documents/ --reset

LLM_PROVIDER=extractive .venv/bin/uvicorn app.main:app --port 8000
```

Open <http://localhost:8000>.

For step-by-step setup, loading your own documents, and putting Jarvis on an existing
website, see **[INSTRUCTION.md](INSTRUCTION.md)**.

Set `ADMIN_API_KEY` in `.env` before using the document endpoints — they fail closed with
503 while it is still the placeholder, rather than leaving document management open.

Embeddings run on your machine by default, so indexing and search need no key at all. Only
answer generation does: set `OPENAI_API_KEY` in `.env` and drop `LLM_PROVIDER=extractive`.

### The offline providers

| Setting | What it is | Trade-off |
|---|---|---|
| `EMBEDDING_PROVIDER=local` (default) | `BAAI/bge-small-en-v1.5` via ONNX, 384 dimensions | Free and offline, with real semantic matching. ~130 MB model, downloaded once |
| `EMBEDDING_PROVIDER=openai` | `text-embedding-3-small`, 1536 dimensions | Needs API credit, and a migration back to 1536 plus a re-index |
| `EMBEDDING_PROVIDER=hashing` | Feature-hashed bag of words | Tests only. Cannot match a paraphrase |
| `LLM_PROVIDER=extractive` | Sentence selection from retrieved context | Runs with no key, and gives the eval a non-LLM baseline — "the model scores X" means little without "selection alone scores Y" |

`fastembed` is used rather than `sentence-transformers`, which pulls in PyTorch at roughly
2 GB for inference this size does not need.

The extractive answerer is genuinely weak: it cannot paraphrase, aggregate two sources, or
refuse reliably. That gap is the measurement, so it is not dressed up.

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

`EMBEDDING_PROVIDER=local`, `LLM_PROVIDER=extractive`, floor 0.60, top_k 5, 75 chunks,
72 golden cases:

| Metric | Result |
|---|---|
| Page hit@5 | 88.5% (54/61) |
| Document hit@5 | 95.1% (58/61) |
| Top-1 document correct | 86.9% (53/61) |
| Over-refusal | 3.3% (2/61) |
| Refusal accuracy, gate only | 18.2% (2/11) |
| Refusal accuracy, end to end | 54.5% (6/11) |
| **Citations resolvable** | **72/72** |
| **Version leaks** | **0** |
| Follow-ups answered correctly | 1/5 |
| Faithfulness (LLM-as-judge) | needs API credit — neither offline provider can judge |

### What the embedding model is worth

The same corpus, same golden set, same code — only the embedding provider changed:

| | hashing (bag of words) | local (bge-small) |
|---|---|---|
| Page hit@5 | 70.5% | **88.5%** |
| Top-1 document correct | 52.5% | **86.9%** |
| Over-refusal | 13.1% | **3.3%** |
| Version leaks | 0 | 0 |

Top-1 accuracy went from a coin flip to 87%. That is the difference between matching words
and matching meaning: "how much time off do staff get" scores 0.71 against "entitled to 15
days of paid annual leave" under the local model, and near zero under the bag-of-words one,
because the two phrases share no words.

Four results are worth reading closely.

**Refusal happens in two stages.** The gate stops 18.2% of unanswerable questions; end to end
the system refuses 54.5%, because the answerer refuses when the passages do not contain an
answer. The ceiling here is the *extractive* answerer, which is poor at refusing — a real
model should lift it substantially without changing retrieval.

**Citations resolvable is 72/72.** Every citation that reached output mapped to a chunk that
was actually supplied; no invented reference survived, across the whole golden set.

**Version leaks are zero at every threshold.** The active-version filter holds independently
of tuning.

**Follow-ups remain the weak spot** — 1 of 5. They are limited by the offline answerer and its
crude query rewriting, not by embeddings, so this is the metric most likely to move when a
real model is plugged in.

### Calibrating the floor

`CLAUDE.md` §26 suggests `SIMILARITY_THRESHOLD=0.70`. The sweep shows what that does:

| floor | page hit@5 | refusal (gate) | over-refusal |
|---|---|---|---|
| 0.50 | 88.5% | 0.0% | 0.0% |
| **0.60** | **88.5%** | **18.2%** | **3.3%** |
| 0.65 | 80.3% | 27.3% | 6.6% |
| 0.68 | 80.3% | 63.6% | 9.8% |
| 0.75 | 59.0% | 90.9% | 37.7% |

Scores are not comparable across models: the same 0.60 that is well-chosen for bge-small
would refuse almost nothing under the bag-of-words provider, where relevant passages score
around 0.3. That is why the floor is calibrated per provider rather than carried over.

Over-refusal at the gate is the more expensive error, because it is unrecoverable — nothing
retrieved means nothing to answer from. Letting a doubtful passage through is recoverable,
since the answerer refuses too. That asymmetry is why 0.60 is chosen over 0.68 despite 0.68
scoring better on gate-level refusal.

Under the bag-of-words provider, the 0.70 threshold suggested in CLAUDE.md produced 0% page hits and 100% over-refusal — it refused every single question. Cosine scores aren't comparable across
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
.venv/bin/python -m pytest        # 210 tests
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
