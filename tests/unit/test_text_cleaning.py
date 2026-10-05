"""Cleaning rules, tested on strings rather than PDFs.

These are the artefacts that silently degrade retrieval: a footer repeated on
every page becomes a chunk's most distinctive text, and (cid:NN) sequences are
tokens spent on nothing.
"""

from app.rag.cleaning import clean_text, strip_repeated_lines


def test_removes_cid_artifacts():
    assert clean_text("(cid:127) Integrity matters") == "Integrity matters"


def test_collapses_runs_of_whitespace_but_keeps_paragraphs():
    assert clean_text("Policy    statement\n\n\n\nNext  paragraph") == (
        "Policy statement\n\nNext paragraph"
    )


def test_removes_soft_hyphenation_across_line_breaks():
    assert clean_text("compli-\nance obligations") == "compliance obligations"


def test_preserves_real_hyphenated_words():
    assert clean_text("a risk-based approach") == "a risk-based approach"


def test_strips_lines_repeated_on_most_pages():
    pages = [
        "Annual leave entitlement\nJarvis Financial Group — Handbook\nPage 1",
        "Sick leave entitlement\nJarvis Financial Group — Handbook\nPage 2",
        "Pension scheme\nJarvis Financial Group — Handbook\nPage 3",
    ]

    cleaned = strip_repeated_lines(pages)

    assert cleaned == ["Annual leave entitlement", "Sick leave entitlement", "Pension scheme"]


def test_does_not_strip_content_that_merely_repeats_twice_in_a_long_document():
    # "Effective date: 2026-01-01" on 2 of 10 pages is content, not furniture.
    pages = ["Effective date: 2026-01-01"] * 2 + [f"Section {i}" for i in range(8)]

    cleaned = strip_repeated_lines(pages)

    assert cleaned[0] == "Effective date: 2026-01-01"


def test_single_page_document_keeps_everything():
    # With one page there is no repetition to measure, so nothing may be dropped.
    assert strip_repeated_lines(["Title\nFooter text"]) == ["Title\nFooter text"]


def test_strips_a_page_number_footer_from_a_single_page_document():
    """Repetition detection needs three pages, so a one-page policy keeps its
    footer and the footer then appears inside answers. A line carrying "Page N"
    is furniture regardless of how many pages the document has."""
    pages = [
        "Employees are entitled to 15 days.\nJarvis Financial Group — Leave Policy (v2.0) Page 1"
    ]

    assert strip_repeated_lines(pages) == ["Employees are entitled to 15 days."]


def test_strips_page_x_of_y_footers():
    pages = ["Some content here.\nPage 2 of 11"]

    assert strip_repeated_lines(pages) == ["Some content here."]


def test_does_not_strip_a_sentence_that_merely_mentions_a_page():
    # "see page 24" inside a sentence is content, not furniture.
    pages = ["The procedure is described on page 24 of the Employee Handbook and must be followed."]

    assert strip_repeated_lines(pages) == [
        "The procedure is described on page 24 of the Employee Handbook and must be followed."
    ]


def test_only_strips_a_page_marker_near_the_end_of_the_page():
    # A footer sits at the end. A line at the top saying "Page 1" is unusual
    # enough that leaving it is safer than cutting real content.
    pages = ["Page 1\nThis is the opening paragraph of the document and carries real content."]

    assert strip_repeated_lines(pages)[0].startswith("Page 1")
