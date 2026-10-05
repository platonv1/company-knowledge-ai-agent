"""Render the Jarvis Financial Group demo corpus to PDF.

Two things here are deliberate:

1. Headings are rendered as "3. Leave and Time Off" so the chunker's
   numbered-heading heuristic has real structure to find, rather than structure
   that only exists in the generator's data model.
2. Fact page numbers are resolved by reading the rendered PDFs back and
   searching for each fact's anchor. Nothing in the golden set is a hand-typed
   page number, so the eval set cannot drift away from the documents.

Usage:
    python -m scripts.generate_corpus [--output documents] [--facts eval/corpus_facts.yaml]
"""

import argparse
import io
import re
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
import yaml
from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    TableStyle,
)
from reportlab.platypus import Table as PdfTable

from scripts.corpus_content import (
    COMPANY,
    FACTS,
    FOLLOWUPS,
    SCANNED_DOCUMENT_FILENAME,
    SCANNED_NOTICE_LINES,
    TEXT_DOCUMENTS,
    UNANSWERABLE,
)
from scripts.corpus_schema import Document, Fact

PAGE_SIZE = A4
MARGIN = 22 * mm


@dataclass(frozen=True)
class GeneratedDocument:
    filename: str
    path: Path
    page_count: int
    title: str
    doc_type: str
    version: str | None
    effective_date: str | None
    doc_status: str


@dataclass(frozen=True)
class ResolvedFact:
    id: str
    question: str
    answer: str
    anchor: str
    document: str
    category: str
    notes: str
    page: int | None


@dataclass(frozen=True)
class CorpusResult:
    documents: list[GeneratedDocument]
    facts: list[ResolvedFact]
    facts_path: Path


def _normalise(text: str) -> str:
    """Collapse whitespace so an anchor can span a rendered line break."""
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------
# Styles
# --------------------------------------------------------------------------


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "DocTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "DocSubtitle",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=12,
            leading=16,
            textColor=colors.HexColor("#444444"),
            spaceAfter=14,
        ),
        "meta": ParagraphStyle(
            "DocMeta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#555555"),
        ),
        "heading": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=18,
            spaceBefore=16,
            spaceAfter=7,
            textColor=colors.HexColor("#102a43"),
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=16,
            alignment=TA_JUSTIFY,
            spaceAfter=9,
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=base["Normal"], fontName="Helvetica", fontSize=10.5, leading=15.5
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=13,
            spaceBefore=8,
            spaceAfter=5,
        ),
    }


def _footer(document: Document):
    label = f"{COMPANY} — {document.title}"
    if document.version:
        label += f" (v{document.version})"

    def draw(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawString(MARGIN, 12 * mm, label)
        canvas.drawRightString(PAGE_SIZE[0] - MARGIN, 12 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    return draw


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def _render_table(table, styles) -> list:
    data = [[Paragraph(f"<b>{c}</b>", styles["bullet"]) for c in table.columns]]
    data += [[Paragraph(str(cell), styles["bullet"]) for cell in row] for row in table.rows]

    available = PAGE_SIZE[0] - 2 * MARGIN
    col_width = available / len(table.columns)

    pdf_table = PdfTable(data, colWidths=[col_width] * len(table.columns), repeatRows=1)
    pdf_table.setStyle(
        TableStyle(
            [
                # Ruling lines on every cell: pdfplumber's default table detection
                # is line-based, so a borderless table would not be found at all.
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return [Paragraph(table.caption, styles["caption"]), pdf_table, Spacer(1, 10)]


def render_document(document: Document, path: Path) -> int:
    """Render one document and return its page count."""
    styles = _styles()
    story: list = [
        Paragraph(COMPANY, styles["meta"]),
        Spacer(1, 4),
        Paragraph(document.title, styles["title"]),
    ]
    if document.subtitle:
        story.append(Paragraph(document.subtitle, styles["subtitle"]))

    meta_bits = [f"Document type: {document.doc_type}"]
    if document.version:
        meta_bits.append(f"Version: {document.version}")
    if document.effective_date:
        meta_bits.append(f"Effective date: {document.effective_date}")
    meta_bits.append(f"Status: {document.doc_status.upper()}")
    story.append(Paragraph(" &nbsp;|&nbsp; ".join(meta_bits), styles["meta"]))
    story.append(Spacer(1, 16))

    for section in document.sections:
        story.append(Paragraph(f"{section.number}. {section.heading}", styles["heading"]))
        for paragraph in section.paragraphs:
            story.append(Paragraph(paragraph, styles["body"]))
        if section.bullets:
            story.append(
                ListFlowable(
                    [
                        ListItem(Paragraph(b, styles["bullet"]), leftIndent=14)
                        for b in section.bullets
                    ],
                    bulletType="bullet",
                    # "•" renders but extracts as "(cid:127)" -- an artefact that would
                    # pollute every bulleted chunk. "·" looks the same and extracts cleanly.
                    start="·",
                    bulletFontName="Helvetica",
                    leftIndent=16,
                    spaceAfter=10,
                )
            )
        if section.table:
            story.extend(_render_table(section.table, styles))

    doc_template = SimpleDocTemplate(
        str(path),
        pagesize=PAGE_SIZE,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=f"{COMPANY} — {document.title}",
        author=COMPANY,
    )
    footer = _footer(document)
    doc_template.build(story, onFirstPage=footer, onLaterPages=footer)

    with pdfplumber.open(path) as pdf:
        return len(pdf.pages)


def render_scanned_notice(path: Path) -> int:
    """Render an image-only PDF.

    The text is rasterised with Pillow and placed as an image, so extraction
    returns nothing. This is the silent-failure case ingestion must catch: a
    naive pipeline indexes empty chunks and reports success.
    """
    width, height = 1240, 1754  # ~150 dpi A4
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    y = 260
    for line in SCANNED_NOTICE_LINES:
        if line:
            draw.text((150, y), line, fill="black")
        y += 90

    # Scanner-like artefacts: a border and a faint skewed streak.
    draw.rectangle([60, 60, width - 60, height - 60], outline="black", width=3)
    draw.line([(80, height - 240), (width - 110, height - 215)], fill="#c8c8c8", width=5)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as pdf_canvas

    c = pdf_canvas.Canvas(str(path), pagesize=PAGE_SIZE)
    c.drawImage(ImageReader(buffer), 0, 0, width=PAGE_SIZE[0], height=PAGE_SIZE[1])
    c.showPage()
    c.save()

    with pdfplumber.open(path) as pdf:
        return len(pdf.pages)


# --------------------------------------------------------------------------
# Fact resolution
# --------------------------------------------------------------------------


def resolve_fact_pages(facts: list[Fact], paths: dict[str, Path]) -> list[ResolvedFact]:
    """Find the page each fact's anchor actually landed on."""
    page_text: dict[str, list[str]] = {}
    for filename, path in paths.items():
        with pdfplumber.open(path) as pdf:
            page_text[filename] = [_normalise(page.extract_text() or "") for page in pdf.pages]

    resolved: list[ResolvedFact] = []
    for fact in facts:
        anchor = _normalise(fact.anchor)
        page_number = None
        for index, text in enumerate(page_text.get(fact.document, []), start=1):
            if anchor in text:
                page_number = index
                break
        resolved.append(
            ResolvedFact(
                id=fact.id,
                question=fact.question,
                answer=fact.answer,
                anchor=fact.anchor,
                document=fact.document,
                category=fact.category,
                notes=fact.notes,
                page=page_number,
            )
        )
    return resolved


def write_facts_file(
    path: Path, documents: list[GeneratedDocument], facts: list[ResolvedFact]
) -> None:
    payload = {
        "company": COMPANY,
        "note": (
            "Generated by scripts/generate_corpus.py. Page numbers are resolved from the "
            "rendered PDFs, never typed by hand. Regenerate rather than edit."
        ),
        "documents": [
            {
                "filename": d.filename,
                "title": d.title,
                "doc_type": d.doc_type,
                "version": d.version,
                "effective_date": d.effective_date,
                "doc_status": d.doc_status,
                "page_count": d.page_count,
            }
            for d in documents
        ],
        "facts": [
            {
                "id": f.id,
                "question": f.question,
                "answer": f.answer,
                "document": f.document,
                "page": f.page,
                "category": f.category,
                **({"notes": f.notes} if f.notes else {}),
            }
            for f in facts
        ],
        "unanswerable": [
            {"id": u.id, "question": u.question, "reason": u.reason} for u in UNANSWERABLE
        ],
        "followups": [
            {
                "id": f.id,
                "turns": f.turns,
                "answer_contains": f.answer_contains,
                "document": f.document,
            }
            for f in FOLLOWUPS
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=100, allow_unicode=True))


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def generate_corpus(output_dir: Path, facts_path: Path | None = None) -> CorpusResult:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated: list[GeneratedDocument] = []
    paths: dict[str, Path] = {}

    for document in TEXT_DOCUMENTS:
        path = output_dir / document.filename
        page_count = render_document(document, path)
        paths[document.filename] = path
        generated.append(
            GeneratedDocument(
                filename=document.filename,
                path=path,
                page_count=page_count,
                title=document.title,
                doc_type=document.doc_type,
                version=document.version,
                effective_date=document.effective_date,
                doc_status=document.doc_status,
            )
        )

    scanned_path = output_dir / SCANNED_DOCUMENT_FILENAME
    scanned_pages = render_scanned_notice(scanned_path)
    generated.append(
        GeneratedDocument(
            filename=SCANNED_DOCUMENT_FILENAME,
            path=scanned_path,
            page_count=scanned_pages,
            title="Notice to Customers",
            doc_type="Notice",
            version=None,
            effective_date="2026-03-01",
            doc_status="active",
        )
    )

    facts = resolve_fact_pages(FACTS, paths)
    resolved_facts_path = Path(facts_path) if facts_path else output_dir / "corpus_facts.yaml"
    write_facts_file(resolved_facts_path, generated, facts)

    return CorpusResult(documents=generated, facts=facts, facts_path=resolved_facts_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the demo corpus.")
    parser.add_argument("--output", default="documents", type=Path)
    parser.add_argument("--facts", default=Path("eval/corpus_facts.yaml"), type=Path)
    args = parser.parse_args()

    result = generate_corpus(args.output, args.facts)

    print(f"Generated {len(result.documents)} documents in {args.output}/")
    for doc in sorted(result.documents, key=lambda d: d.filename):
        flag = "" if doc.doc_status == "active" else "  [ARCHIVED]"
        print(f"  {doc.filename:<38} {doc.page_count:>3} pages{flag}")

    missing = [f.id for f in result.facts if f.page is None]
    print(f"\nResolved {len(result.facts) - len(missing)}/{len(result.facts)} fact anchors")
    if missing:
        raise SystemExit(f"ERROR: anchors not found in rendered PDFs: {missing}")
    print(f"Wrote {result.facts_path}")


if __name__ == "__main__":
    main()
