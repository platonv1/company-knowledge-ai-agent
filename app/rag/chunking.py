"""Structure-aware chunking.

Splitting on character count alone (CLAUDE.md s8 warns against it) severs
policies mid-clause and strands table rows from their headers. This chunker
works in three passes:

1. Parse pages into blocks -- paragraphs and tables -- tracking the heading
   each block sits under and the page it came from.
2. Group consecutive blocks by section.
3. Pack each section's blocks into token-bounded chunks, never splitting a
   table that fits, and repeating the header when one does not.

Heading detection covers numbered headings ("3.2 Annual Leave") and ALL-CAPS
headings. Title-Case detection from the original plan is deliberately omitted:
on real prose it fires on ordinary sentence fragments ("Group Tax function
approval"), and a false heading fragments a section far more damagingly than a
missed one merges two.
"""

import hashlib
import re
from dataclasses import dataclass, field

from app.rag.extraction import ExtractedDocument, ExtractedTable
from app.rag.tokenizer import count_tokens, split_by_tokens, take_last_tokens

_NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.{0,78})$")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
MAX_HEADING_WORDS = 14


@dataclass(frozen=True)
class ChunkConfig:
    target_tokens: int = 600
    max_tokens: int = 800
    overlap_ratio: float = 0.12

    @property
    def overlap_tokens(self) -> int:
        return int(self.target_tokens * self.overlap_ratio)


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    content: str
    token_count: int
    page_start: int
    page_end: int
    section_path: str | None
    content_hash: str


@dataclass
class _Block:
    content: str
    page_start: int
    page_end: int
    section_path: str | None
    is_table: bool = False
    table: ExtractedTable | None = None
    tokens: int = field(default=0)

    def __post_init__(self) -> None:
        self.tokens = count_tokens(self.content)


# --------------------------------------------------------------------------
# Pass 1 -- parse into blocks
# --------------------------------------------------------------------------


def _match_heading(line: str) -> tuple[int, str] | None:
    """Return (depth, heading text) if the line looks like a heading."""
    stripped = line.strip()
    if not stripped or stripped.endswith((".", ":", ";", ",")):
        return None

    numbered = _NUMBERED_HEADING.match(stripped)
    if numbered:
        number, title = numbered.groups()
        if len(title.split()) <= MAX_HEADING_WORDS:
            # Keep the heading exactly as the document writes it. Reformatting it
            # turns "3.2 Annual Leave" into "3.2. Annual Leave", so the section
            # path stops matching the text a reader sees on the page.
            return len(number.split(".")), stripped

    words = stripped.split()
    if (
        2 <= len(words) <= MAX_HEADING_WORDS
        and stripped == stripped.upper()
        and any(c.isalpha() for c in stripped)
        and len(stripped) <= 60
    ):
        return 1, stripped

    return None


def _section_path(stack: dict[int, str]) -> str | None:
    if not stack:
        return None
    return " / ".join(stack[depth] for depth in sorted(stack))


def _parse_blocks(document: ExtractedDocument) -> list[_Block]:
    blocks: list[_Block] = []
    stack: dict[int, str] = {}

    pending: list[str] = []
    pending_pages: set[int] = set()

    def flush_paragraph() -> None:
        nonlocal pending, pending_pages
        text = " ".join(pending).strip()
        if text:
            blocks.append(
                _Block(
                    content=text,
                    page_start=min(pending_pages),
                    page_end=max(pending_pages),
                    section_path=_section_path(stack),
                )
            )
        pending = []
        pending_pages = set()

    for page in document.pages:
        for line in page.text.split("\n"):
            stripped = line.strip()
            if not stripped:
                flush_paragraph()
                continue

            heading = _match_heading(stripped)
            if heading:
                flush_paragraph()
                depth, text = heading
                # Entering a shallower heading clears the deeper levels.
                for existing in [d for d in stack if d >= depth]:
                    del stack[existing]
                stack[depth] = text
                continue

            pending.append(stripped)
            pending_pages.add(page.page_number)

        flush_paragraph()

        # Tables were lifted out of the page text, so they attach to whichever
        # section was open when the page ended.
        for table in page.tables:
            markdown = table.to_markdown()
            if markdown.strip():
                blocks.append(
                    _Block(
                        content=markdown,
                        page_start=page.page_number,
                        page_end=page.page_number,
                        section_path=_section_path(stack),
                        is_table=True,
                        table=table,
                    )
                )

    return blocks


# --------------------------------------------------------------------------
# Pass 3 -- pack blocks into chunks
# --------------------------------------------------------------------------


def _split_table(block: _Block, config: ChunkConfig) -> list[_Block]:
    """Split an oversized table, repeating the header in every part.

    Rows without their header are uninterpretable, which is worse than a
    slightly oversized chunk.
    """
    table = block.table
    assert table is not None

    header_lines = [
        "| " + " | ".join(table.header) + " |",
        "| " + " | ".join("---" for _ in table.header) + " |",
    ]
    header_tokens = count_tokens("\n".join(header_lines))

    parts: list[_Block] = []
    current: list[str] = []
    current_tokens = header_tokens

    def flush() -> None:
        nonlocal current, current_tokens
        if current:
            parts.append(
                _Block(
                    content="\n".join(header_lines + current),
                    page_start=block.page_start,
                    page_end=block.page_end,
                    section_path=block.section_path,
                    is_table=True,
                    table=table,
                )
            )
        current = []
        current_tokens = header_tokens

    for row in table.rows:
        line = "| " + " | ".join(row) + " |"
        row_tokens = count_tokens(line)
        if current and current_tokens + row_tokens > config.max_tokens:
            flush()
        current.append(line)
        current_tokens += row_tokens

    flush()
    return parts


def _split_text(block: _Block, config: ChunkConfig) -> list[_Block]:
    """Split an oversized paragraph on sentence boundaries where possible."""
    pieces: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for sentence in _SENTENCE_BREAK.split(block.content):
        sentence = sentence.strip()
        if not sentence:
            continue
        tokens = count_tokens(sentence)
        if tokens > config.max_tokens:
            if current:
                pieces.append(" ".join(current))
                current, current_tokens = [], 0
            pieces.extend(split_by_tokens(sentence, config.max_tokens))
            continue
        if current and current_tokens + tokens > config.max_tokens:
            pieces.append(" ".join(current))
            current, current_tokens = [], 0
        current.append(sentence)
        current_tokens += tokens

    if current:
        pieces.append(" ".join(current))

    return [
        _Block(
            content=piece,
            page_start=block.page_start,
            page_end=block.page_end,
            section_path=block.section_path,
        )
        for piece in pieces
        if piece.strip()
    ]


def _normalise_block_sizes(blocks: list[_Block], config: ChunkConfig) -> list[_Block]:
    normalised: list[_Block] = []
    for block in blocks:
        if block.tokens <= config.max_tokens:
            normalised.append(block)
        elif block.is_table:
            normalised.extend(_split_table(block, config))
        else:
            normalised.extend(_split_text(block, config))
    return normalised


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def chunk_document(
    document: ExtractedDocument,
    document_title: str,
    config: ChunkConfig | None = None,
) -> list[TextChunk]:
    """Chunk an extracted document into retrievable units."""
    config = config or ChunkConfig()
    blocks = _normalise_block_sizes(_parse_blocks(document), config)
    if not blocks:
        return []

    chunks: list[TextChunk] = []
    buffer: list[_Block] = []
    buffer_tokens = 0
    carry_over = ""

    def flush() -> None:
        nonlocal buffer, buffer_tokens, carry_over
        if not buffer:
            return

        body = "\n\n".join(block.content for block in buffer)
        content = f"{carry_over}\n\n{body}".strip() if carry_over else body

        chunks.append(
            TextChunk(
                chunk_index=len(chunks),
                content=content,
                token_count=count_tokens(content),
                page_start=min(block.page_start for block in buffer),
                page_end=max(block.page_end for block in buffer),
                section_path=buffer[0].section_path,
                content_hash=_hash(content),
            )
        )

        # Overlap is drawn from the trailing text block only. Carrying table rows
        # forward would index the same rows twice and return near-duplicates.
        last = buffer[-1]
        carry_over = "" if last.is_table else take_last_tokens(last.content, config.overlap_tokens)
        buffer = []
        buffer_tokens = 0

    for block in blocks:
        starts_new_section = buffer and block.section_path != buffer[-1].section_path
        would_overflow = buffer and buffer_tokens + block.tokens > config.target_tokens

        if starts_new_section:
            flush()
            carry_over = ""  # overlap must not leak across section boundaries
        elif would_overflow:
            flush()

        buffer.append(block)
        buffer_tokens += block.tokens

    flush()
    return chunks


def embedding_text(chunk: TextChunk, document_title: str) -> str:
    """The text actually sent to the embedding model.

    A bare paragraph loses the context a reader gets from the page around it, so
    the document title and section path are prepended. The stored `content` stays
    clean for display and citation.
    """
    header = document_title
    if chunk.section_path:
        header = f"{document_title} — {chunk.section_path}"
    return f"{header}\n\n{chunk.content}"
