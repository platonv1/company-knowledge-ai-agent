# Running and Embedding Jarvis

How to start the chatbot, load your own documents, and put it on an existing website.

Every command and snippet here was run against this codebase. Where something does not work
yet, it says so rather than describing an intention.

- [1. Before you start](#1-before-you-start)
- [2. Run it locally](#2-run-it-locally)
- [3. Switch to real models](#3-switch-to-real-models)
- [4. Load your own documents](#4-load-your-own-documents)
- [5. Check it is working](#5-check-it-is-working)
- [6. Embed it in an existing website](#6-embed-it-in-an-existing-website)
- [7. Before you put it on a public site](#7-before-you-put-it-on-a-public-site)
- [8. Configuration reference](#8-configuration-reference)
- [9. Troubleshooting](#9-troubleshooting)

---

## 1. Before you start

| You need | Why | Check |
|---|---|---|
| Docker | Runs Postgres with the pgvector extension | `docker --version` |
| Python 3.12 | 3.13+ is untested here; some dependencies lag | `python3.12 --version` |
| An OpenAI API key | Only for real answer quality — see below | — |

**You do not need an API key to run this.** The project ships offline providers for both
embedding and answering, so you can start it, ingest documents, ask questions and run the
evaluation with no account anywhere. Answer quality is much lower; section 3 covers the swap.

---

## 2. Run it locally

### Step 1 — Start the database

```bash
docker compose up -d
```

Postgres listens on **5433** (not 5432) to avoid clashing with a local Postgres you may
already have. Wait for it to report healthy:

```bash
docker inspect --format='{{.State.Health.Status}}' jarvis-db
```

### Step 2 — Install dependencies

```bash
python3.12 -m venv .venv          # or: uv venv --python python3.12 .venv
.venv/bin/pip install -r requirements-dev.txt
```

### Step 3 — Create your configuration

```bash
cp .env.example .env
```

Open `.env` and set `ADMIN_API_KEY` to anything you like. Until you do, the document
management endpoints refuse every request with `503` — they fail closed rather than leaving
document management open.

### Step 4 — Create the database tables

```bash
.venv/bin/alembic upgrade head
```

### Step 5 — Generate the demo documents

```bash
.venv/bin/python -m scripts.generate_corpus
```

This writes 13 PDFs for a fictional bank into `documents/`. One of them,
`Scanned_Notice.pdf`, is deliberately image-only — it is there to prove the system rejects
documents it cannot read instead of indexing them as empty.

Skip this step if you are going straight to your own documents (section 4).

### Step 6 — Index the documents

```bash
EMBEDDING_PROVIDER=hashing \
  .venv/bin/python -m scripts.ingest_documents documents/ --reset
```

Expected output ends with:

```
Indexed 75 chunks for Jarvis Financial Group.
1 document(s) failed. A scanned document failing here is expected; anything else is not.
```

`Scanned_Notice.pdf` failing is correct. Any other failure is not.

### Step 7 — Start the server

```bash
EMBEDDING_PROVIDER=hashing RELEVANCE_FLOOR=0.20 LLM_PROVIDER=extractive \
  .venv/bin/uvicorn app.main:app --port 8000
```

Open **<http://localhost:8000>**.

> The three overrides select the offline providers and the relevance floor calibrated for
> them. Drop all three once you have an API key — see the next section.

---

## 3. Switch to real models

The offline providers exist so the project runs with no account. They are not good:

| Provider | What it does | What it cannot do |
|---|---|---|
| `hashing` embeddings | Matches on shared words | Recognise that "time off" and "annual leave" mean the same thing |
| `extractive` answering | Picks the sentences with the most words in common | Paraphrase, combine two sources, or answer a question worded differently from the document |

To use real models, put a key in `.env`:

```bash
OPENAI_API_KEY=sk-...your-key...
```

Then **re-index** and start without the overrides:

```bash
.venv/bin/python -m scripts.ingest_documents documents/ --reset
.venv/bin/uvicorn app.main:app --port 8000
```

**Re-indexing is required, not optional.** Vectors from different embedding models are not
comparable. If you switch provider without re-indexing, search returns nonsense while
appearing to work.

### Calibrate the relevance floor

`RELEVANCE_FLOOR` decides when Jarvis says "I couldn't find that". The right value depends on
the embedding model, so measure it rather than guess:

```bash
.venv/bin/python -m scripts.run_eval --sweep
```

Pick the row with the best page-hit rate at an acceptable over-refusal rate, and set
`RELEVANCE_FLOOR` in `.env`. The shipped default for OpenAI is `0.35`, which is an estimate
until you run this.

For context, on the offline provider the sweep shows `0.70` — the value suggested in
`CLAUDE.md` — produces **0% page hits and 100% over-refusal**. Jarvis refuses every question.
Do not set a floor without measuring it.

---

## 4. Load your own documents

Only text-based PDFs work. Scanned PDFs are rejected with a clear error; there is no OCR.

### From the command line

```bash
.venv/bin/python -m scripts.ingest_documents /path/to/your/pdfs/
```

Add `--reset` to clear what is already indexed first. Without it, documents are added to the
existing set, and re-uploading identical bytes is skipped.

### Through the API

```bash
curl -X POST http://localhost:8000/api/documents \
  -H "X-Admin-Key: your-admin-key" \
  -F "file=@/path/to/Employee_Handbook.pdf"
```

List what is indexed, with any failure reason:

```bash
curl -H "X-Admin-Key: your-admin-key" http://localhost:8000/api/documents
```

### Replacing a superseded policy

Archive the old version rather than deleting it. Archiving removes it from retrieval but keeps
the record:

```bash
curl -X POST http://localhost:8000/api/documents/{id}/archive \
  -H "X-Admin-Key: your-admin-key"
```

This matters more than it sounds. On the demo corpus, the archived 2025 leave policy scores
*higher* on raw similarity than the active 2026 one. Without archiving, Jarvis answers from
the superseded document and cites a real page while doing it.

### Document metadata

Jarvis reads metadata from a line near the top of each document, if present:

```
Document type: HR Policy | Version: 2.0 | Effective date: 2026-01-01 | Status: ACTIVE
```

`Status: ARCHIVED` marks a document as superseded at ingest time. If the line is absent,
everything defaults sensibly and the title is taken from the filename.

---

## 5. Check it is working

```bash
curl http://localhost:8000/api/health
```

```json
{"status":"ok","checks":{"knowledge_base":{"chunk_count":75,"document_count":12,"failed_count":1}}}
```

`document_count` counts only documents Jarvis can actually answer from. `failed_count` is
documents that failed ingestion — check those with `GET /api/documents`.

Ask a question:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"How many annual leave days do employees get?"}'
```

Two things to confirm in the response:

- `"grounded": true` and a non-empty `sources` array
- asking something the documents do not cover returns `"grounded": false` with no sources,
  rather than a confident guess

---

## 6. Embed it in an existing website

> **There is no `jarvis.js` widget.** The embeddable script widget is listed as not built in
> the README. What follows works today using the chat page the server already serves.

First, host Jarvis somewhere the visitor's browser can reach, over HTTPS, and note the origin
(for example `https://jarvis.yourcompany.com`). The examples below use
`http://localhost:8000` so you can try them immediately.

### Option A — Floating panel (recommended)

Paste this before `</body>` on your site and change one line, `JARVIS_ORIGIN`. It adds a
launcher button that opens Jarvis in a panel.

```html
<script>
(() => {
  const JARVIS_ORIGIN = "https://jarvis.yourcompany.com";   // <- change this

  const launcher = document.createElement("button");
  launcher.type = "button";
  launcher.setAttribute("aria-expanded", "false");
  launcher.setAttribute("aria-label", "Ask Jarvis");
  launcher.textContent = "Ask Jarvis";
  Object.assign(launcher.style, {
    position: "fixed", right: "20px", bottom: "20px", zIndex: "2147483000",
    font: "500 15px/1 system-ui, sans-serif", color: "#fff", background: "#143d32",
    border: "0", borderRadius: "999px", padding: "14px 20px", cursor: "pointer",
    boxShadow: "0 6px 20px rgba(0,0,0,.22)",
  });

  const panel = document.createElement("iframe");
  panel.src = JARVIS_ORIGIN + "/";
  panel.title = "Jarvis — company knowledge assistant";
  panel.setAttribute("loading", "lazy");
  Object.assign(panel.style, {
    position: "fixed", right: "20px", bottom: "84px", zIndex: "2147483000",
    width: "min(420px, calc(100vw - 40px))", height: "min(640px, calc(100vh - 120px))",
    border: "1px solid rgba(0,0,0,.18)", borderRadius: "10px", background: "#fff",
    boxShadow: "0 18px 48px rgba(0,0,0,.26)", display: "none",
  });

  launcher.addEventListener("click", () => {
    const open = panel.style.display === "none";
    panel.style.display = open ? "block" : "none";
    launcher.setAttribute("aria-expanded", String(open));
    launcher.textContent = open ? "Close" : "Ask Jarvis";
  });

  document.body.append(panel, launcher);
})();
</script>
```

**This needs no CORS configuration.** The chat page runs inside the iframe and calls the API
on its own origin, so your site's origin is never involved. Verified: the panel answers
correctly from a site whose origin is not in `CORS_ALLOWED_ORIGINS`.

An iframe is used rather than injecting Jarvis into your page because it isolates styling in
both directions — your CSS cannot break Jarvis, and Jarvis cannot leak styles into your page.

### Option B — Inline on a page

To place Jarvis in a help centre or contact page instead of a floating panel:

```html
<iframe
  src="https://jarvis.yourcompany.com/"
  title="Jarvis — company knowledge assistant"
  style="width:100%; height:640px; border:1px solid #d8ddda; border-radius:10px;"
  loading="lazy">
</iframe>
```

### Option C — Your own interface, calling the API

Use this only if you need the chat UI to match your design system. You build the whole
interface; Jarvis provides the answers.

```js
const response = await fetch("https://jarvis.yourcompany.com/api/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    message: "How many annual leave days do employees get?",
    conversation_id: savedConversationId,   // omit on the first message
  }),
});

const { answer, sources, conversation_id, grounded } = await response.json();
```

| Field | Use it for |
|---|---|
| `answer` | The reply. Contains `[S1]` markers matching `sources`. **Insert as text, never as HTML.** |
| `sources` | `document`, `page_label`, `section`, `version` for each citation |
| `conversation_id` | Send it back on the next message so follow-ups resolve |
| `grounded` | `false` means Jarvis found nothing — show it as a distinct state, not as an answer |

**Option C requires CORS.** Add your site's origin to `.env`:

```bash
CORS_ALLOWED_ORIGINS=https://www.yourcompany.com,https://yourcompany.com
```

List every origin your pages are served from. `https://yourcompany.com` and
`https://www.yourcompany.com` are different origins. Requests from an origin not on the list
are rejected before they reach the chatbot.

Handle `429` responses — the API rate limits per IP and returns a `Retry-After` header in
seconds.

---

## 7. Before you put it on a public site

`POST /api/chat` has **no authentication**, because a public website widget cannot carry a
secret. Anyone who finds the URL can send it questions, and every question costs you money at
your model provider. Work through this list before exposing it:

- [ ] **Serve over HTTPS.** The API accepts and returns no secrets, but the questions people
      ask are often sensitive.
- [ ] **Set `CORS_ALLOWED_ORIGINS`** to your real origins. Never leave it permissive.
- [ ] **Set `ADMIN_API_KEY`** to a long random value. With the placeholder, the document
      endpoints return 503 and are unusable; with a weak value, anyone can delete your
      knowledge base.
- [ ] **Tune `CHAT_RATE_LIMIT_PER_MINUTE`.** The default is 20 per IP per minute.
- [ ] **Run one instance, or add Redis.** The rate limiter counts in process memory. Behind a
      load balancer, each instance keeps its own count, so the effective limit multiplies by
      the number of instances.
- [ ] **Review what you index.** Anything in the knowledge base can be quoted to any visitor.
      There is no per-user access control — that is listed as not built.
- [ ] **Put a CDN or WAF in front of it** if the site gets real traffic.

---

## 8. Configuration reference

Set these in `.env`, or as environment variables, which take precedence.

| Variable | Default | What it does |
|---|---|---|
| `DATABASE_URL` | Postgres on 5433 | Where documents, chunks and conversations live |
| `OPENAI_API_KEY` | — | Required unless using the offline providers |
| `LLM_PROVIDER` | `openai` | `openai` or `extractive` (offline) |
| `LLM_MODEL` | `gpt-4o` | Model used to write answers |
| `LLM_FAST_MODEL` | `gpt-4o-mini` | Cheaper model used only to rewrite follow-up questions |
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `hashing` (offline) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Changing this requires a full re-index |
| `RELEVANCE_FLOOR` | `0.35` | Below this, Jarvis refuses. **Calibrate per embedding model** |
| `TOP_K` | `5` | Passages sent to the model |
| `SEARCH_K` | `8` | Passages retrieved before filtering |
| `CHUNK_TARGET_TOKENS` | `600` | Passage size. Changing it requires a re-index |
| `HISTORY_WINDOW_MESSAGES` | `6` | Messages used to resolve follow-up questions |
| `ADMIN_API_KEY` | placeholder | Required for all document endpoints |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:8000` | Origins allowed to call the API directly |
| `CHAT_RATE_LIMIT_PER_MINUTE` | `20` | Requests per IP per minute |
| `COMPANY_NAME` | `Jarvis Financial Group` | Shown in the interface and the system prompt |
| `JARVIS_NAME` | `Jarvis` | The assistant's name |

---

## 9. Troubleshooting

**The page says "No documents indexed yet"**
Nothing is in the knowledge base. Run step 6. Confirm with `curl localhost:8000/api/health`.

**Every question is refused**
`RELEVANCE_FLOOR` is too high for your embedding provider, or you changed embedding provider
without re-indexing. Run `python -m scripts.run_eval --sweep` and set the floor from the
results. With `EMBEDDING_PROVIDER=hashing`, use `0.20`, not the `0.35` default.

**Answers are irrelevant or scrambled**
Almost always a provider change without re-indexing. Re-run ingestion with `--reset`.

**`502` from `/api/chat`**
Jarvis could not reach the model provider. Check `OPENAI_API_KEY`, or run with
`LLM_PROVIDER=extractive` to confirm the rest of the pipeline is fine.

**`503` from the document endpoints**
`ADMIN_API_KEY` is unset or still `change-me-in-production`. It fails closed by design.

**A document shows `failed`**
Check the reason: `curl -H "X-Admin-Key: ..." localhost:8000/api/documents`. The usual cause is
a scanned PDF with no text layer. There is no OCR — re-export the PDF with real text.

**The embedded panel is blank**
Open the Jarvis origin directly in a browser tab. If that fails, the problem is the server or
the URL, not the embed. If the page loads alone but not in the frame, something in front of
Jarvis — a CDN, proxy or WAF — is adding `X-Frame-Options` or a `frame-ancestors` policy. The
application sets neither.

**Calls from my own JavaScript are blocked by CORS**
Your origin is not in `CORS_ALLOWED_ORIGINS`. Include the scheme and any `www.` variant.
Option A does not need this; only Option C does.

**`HEAD` requests return 405**
`HEAD /` and `HEAD /api/health` return `405 Method Not Allowed` — the routes are declared
GET-only. Configure uptime monitors and load balancer probes to use **GET**. If you need HEAD,
change the health route to `@router.api_route("/health", methods=["GET", "HEAD"])`.

**Tests wipe my documents**
They should not — the test suite uses a separate `jarvis_test` database. If it happens, check
`DATABASE_URL` is not overridden in your shell.

---

## What is not built

Named here so you do not go looking: a drop-in `jarvis.js` script widget, an admin web
console, per-user or role-based access to documents, OCR for scanned PDFs, multi-tenancy for
several companies on one deployment, and hybrid or reranked search. The README lists these
under "Not built".
