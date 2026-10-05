/* Jarvis chat client.
 *
 * No build step and no framework: the eventual embeddable widget has to be
 * dependency-light, and this is the code that becomes it.
 *
 * The one rule worth stating: answer text from the API is inserted as text
 * nodes, never as HTML. The text passes through a language model and originates
 * in uploaded documents, so treating it as markup would be an injection path
 * straight into the page.
 */

(() => {
  "use strict";

  const API = { chat: "/api/chat", health: "/api/health" };

  const form = document.getElementById("ask");
  const input = document.getElementById("question");
  const send = document.getElementById("send");
  const transcript = document.getElementById("transcript");
  const opening = document.getElementById("opening");
  const holding = document.getElementById("holding");
  const exchangeTemplate = document.getElementById("tpl-exchange");
  const refTemplate = document.getElementById("tpl-ref");

  let conversationId = null;
  let inFlight = false;

  /* ---------- knowledge base status ---------- */

  async function reportHolding() {
    try {
      const response = await fetch(API.health);
      const body = await response.json();
      const kb = body.checks && body.checks.knowledge_base;

      if (body.status !== "ok" || !kb) {
        holding.dataset.state = "down";
        holding.textContent = "The knowledge base is unavailable.";
        return;
      }
      if (!kb.document_count) {
        holding.dataset.state = "down";
        holding.textContent = "No documents indexed yet.";
        return;
      }

      // The count is the product's claim: Jarvis speaks only from these.
      holding.replaceChildren(
        document.createTextNode("Answering from "),
        strong(`${kb.document_count} controlled document${kb.document_count === 1 ? "" : "s"}`),
        document.createTextNode(` · ${kb.chunk_count} indexed passages`)
      );
    } catch {
      holding.dataset.state = "down";
      holding.textContent = "Could not reach the knowledge base.";
    }
  }

  function strong(text) {
    const el = document.createElement("strong");
    el.textContent = text;
    return el;
  }

  /* ---------- rendering ---------- */

  /* Splits the answer on [S1] / [S1, S2] markers so they can be styled as
   * citations. Everything else is appended as a text node. */
  function renderAnswer(container, answer) {
    container.replaceChildren();
    const pattern = /\[\s*S\d+(?:\s*,\s*S\d+)*\s*\]/g;

    for (const paragraph of answer.split(/\n{2,}/)) {
      const p = document.createElement("p");
      let cursor = 0;
      let match;
      pattern.lastIndex = 0;

      while ((match = pattern.exec(paragraph)) !== null) {
        if (match.index > cursor) {
          p.appendChild(document.createTextNode(paragraph.slice(cursor, match.index)));
        }
        const cite = document.createElement("span");
        cite.className = "cite";
        cite.textContent = match[0].replace(/[[\]\s]/g, "");
        p.appendChild(cite);
        cursor = match.index + match[0].length;
      }
      if (cursor < paragraph.length) {
        p.appendChild(document.createTextNode(paragraph.slice(cursor)));
      }
      container.appendChild(p);
    }
  }

  function renderReferences(list, sources) {
    list.replaceChildren();
    for (const source of sources) {
      const node = refTemplate.content.cloneNode(true);
      node.querySelector(".ref__marker").textContent = source.marker;
      node.querySelector(".ref__title").textContent = source.document_title || source.document;

      const bits = [source.document, `page ${source.page_label || source.page}`];
      if (source.section) bits.push(source.section);
      if (source.version) bits.push(`version ${source.version}`);
      node.querySelector(".ref__meta").textContent = bits.join(" · ");

      list.appendChild(node);
    }
  }

  function startExchange(question) {
    const node = exchangeTemplate.content.cloneNode(true);
    const record = node.querySelector(".record");
    record.querySelector(".record__question").textContent = question;

    const answer = record.querySelector(".record__answer");
    const scanning = document.createElement("div");
    scanning.className = "scanning";
    scanning.setAttribute("role", "status");
    scanning.setAttribute("aria-label", "Searching the knowledge base");
    answer.appendChild(scanning);

    transcript.appendChild(node);
    return record;
  }

  function completeExchange(record, body) {
    const answer = record.querySelector(".record__answer");
    answer.dataset.grounded = String(body.grounded);
    renderAnswer(answer, body.answer);

    if (body.sources && body.sources.length) {
      const refs = record.querySelector(".record__refs");
      renderReferences(refs.querySelector(".refs"), body.sources);
      refs.hidden = false;
    }
  }

  function failExchange(record, message) {
    const answer = record.querySelector(".record__answer");
    answer.replaceChildren();
    answer.removeAttribute("data-grounded");
    const note = document.createElement("div");
    note.className = "failure";
    note.textContent = message;
    answer.appendChild(note);
  }

  /* ---------- asking ---------- */

  async function ask(question) {
    if (inFlight) return;
    inFlight = true;
    send.disabled = true;
    opening.hidden = true;

    const record = startExchange(question);
    record.scrollIntoView({ behavior: "smooth", block: "start" });

    try {
      const response = await fetch(API.chat, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: question, conversation_id: conversationId }),
      });

      if (response.status === 429) {
        const wait = response.headers.get("Retry-After") || "a few";
        failExchange(record, `Too many questions at once. Try again in ${wait} seconds.`);
        return;
      }
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        failExchange(record, detail.detail || "Jarvis could not answer that. Try again.");
        return;
      }

      const body = await response.json();
      conversationId = body.conversation_id;
      completeExchange(record, body);
    } catch {
      failExchange(record, "Could not reach Jarvis. Check your connection and try again.");
    } finally {
      inFlight = false;
      send.disabled = false;
      input.focus();
    }
  }

  /* ---------- wiring ---------- */

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) return;
    input.value = "";
    resize();
    ask(question);
  });

  // Enter sends; Shift+Enter adds a line, which is what people expect here.
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  function resize() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 144)}px`;
  }
  input.addEventListener("input", resize);

  for (const starter of document.querySelectorAll(".starter")) {
    starter.addEventListener("click", () => ask(starter.textContent.trim()));
  }

  reportHolding();
  input.focus();
})();
