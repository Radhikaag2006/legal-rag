"""Render a research summary as a Word (.docx) or PDF document."""
import html
import io
import re
from datetime import date

import pymupdf
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

DISCLAIMER = (
    "AI-assisted research based only on the indexed judgments and any documents "
    "uploaded to this chat. Verify every authority against the official report "
    "before relying on it. This is not legal advice."
)
ACCENT = RGBColor(0x1F, 0x4D, 0x46)


# ---------------------------------------------------------
# Parsing (shared by both formats)
# ---------------------------------------------------------

def _plain_cites(text):
    return re.sub(r"\[S(\d+)\]", r"[\1]", text)


def parse_blocks(md):
    """Markdown subset -> [(kind, payload)] with kind in h, p, ul, ol, quote."""
    blocks, para, items, list_kind = [], [], [], None

    def flush_para():
        if para:
            blocks.append(("p", " ".join(para)))
            para.clear()

    def flush_list():
        nonlocal items, list_kind
        if items:
            blocks.append((list_kind, items))
        items, list_kind = [], None

    for raw in md.replace("\r", "").split("\n"):
        line = raw.strip()
        if not line:
            flush_para(); flush_list(); continue
        m = re.match(r"^#{1,4}\s+(.*)$", line)
        if m:
            flush_para(); flush_list(); blocks.append(("h", m.group(1))); continue
        m = re.match(r"^[-*•]\s+(.*)$", line)
        if m:
            flush_para()
            if list_kind != "ul":
                flush_list(); list_kind = "ul"
            items.append(m.group(1)); continue
        m = re.match(r"^\d+[.)]\s+(.*)$", line)
        if m:
            flush_para()
            if list_kind != "ol":
                flush_list(); list_kind = "ol"
            items.append(m.group(1)); continue
        m = re.match(r"^>\s?(.*)$", line)
        if m:
            flush_para(); flush_list(); blocks.append(("quote", m.group(1))); continue
        flush_list(); para.append(line)
    flush_para(); flush_list()
    return blocks


def _runs(text):
    """Inline markdown -> [(text, bold, italic)]."""
    text = _plain_cites(text)
    out = []
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*)", text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            out.append((part[2:-2], True, False))
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append((part[1:-1], False, True))
        else:
            out.append((part.replace("`", ""), False, False))
    return out


def _authority_line(a):
    bits = [a["court"] if a.get("source_type") != "upload" else "Uploaded document"]
    if a.get("date"):
        bits.append(a["date"])
    if a.get("page"):
        bits.append(f"p. {a['page']}")
    line = ", ".join(b for b in bits if b)
    if not a.get("cited", True):
        line += " (retrieved, not cited in the summary)"
    return line


def _today():
    return date.today().strftime("%d %B %Y").lstrip("0")


# ---------------------------------------------------------
# Word
# ---------------------------------------------------------

def _add_runs(paragraph, text):
    for t, bold, italic in _runs(text):
        r = paragraph.add_run(t)
        r.bold, r.italic = bold, italic


def _page_number_field(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = paragraph.add_run("Page ")
    r.font.size = Pt(8.5)
    run = paragraph.add_run()
    run.font.size = Pt(8.5)
    for kind, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = txt
        run._r.append(el)


def to_docx(title, summary, authorities):
    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = sec.right_margin = Pt(64)
    sec.top_margin = sec.bottom_margin = Pt(64)

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    for name, size in (("Heading 1", 14), ("Heading 2", 12.5)):
        st = doc.styles[name]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = ACCENT
        st.paragraph_format.space_before = Pt(14)
        st.paragraph_format.space_after = Pt(4)

    t = doc.add_paragraph()
    r = t.add_run("Research Summary")
    r.bold = True
    r.font.size = Pt(22)
    r.font.color.rgb = ACCENT
    t.paragraph_format.space_after = Pt(2)

    sub = doc.add_paragraph()
    r = sub.add_run(f"{title}  ·  Prepared {_today()}")
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor(0x6B, 0x6E, 0x75)

    for kind, payload in parse_blocks(summary):
        if kind == "h":
            doc.add_heading(_plain_cites(payload), level=1)
        elif kind == "p":
            _add_runs(doc.add_paragraph(), payload)
        elif kind in ("ul", "ol"):
            style = "List Bullet" if kind == "ul" else "List Number"
            for item in payload:
                p = doc.add_paragraph(style=style)
                p.paragraph_format.space_after = Pt(3)
                _add_runs(p, item)
        elif kind == "quote":
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(18)
            _add_runs(p, payload)
            for r in p.runs:
                r.italic = True

    doc.add_heading("Authorities", level=1)
    for a in authorities:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Pt(22)
        p.paragraph_format.first_line_indent = Pt(-22)
        p.paragraph_format.space_after = Pt(5)
        p.add_run(f"[{a['number']}]  ").bold = True
        p.add_run(a["case_title"]).bold = True
        meta = _authority_line(a)
        if meta:
            p.add_run("\n" + meta).font.size = Pt(10)
        link = a.get("external_url")
        if link:
            p.add_run("\n" + link).font.size = Pt(9)

    note = doc.add_paragraph()
    note.paragraph_format.space_before = Pt(16)
    r = note.add_run(DISCLAIMER)
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x6B, 0x6E, 0x75)

    _page_number_field(sec.footer.paragraphs[0])

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------
# PDF
# ---------------------------------------------------------

PDF_CSS = """
body { font-family: sans-serif; font-size: 10.5pt; line-height: 1.4; color: #1e2024; }
h1 { font-size: 22pt; color: #1f4d46; margin: 0 0 2pt 0; }
h2 { font-size: 13.5pt; color: #1f4d46; margin: 14pt 0 4pt 0; }
p { margin: 0 0 6pt 0; }
li { margin: 0 0 3pt 0; }
.sub { color: #6b6e75; font-size: 9.5pt; margin-bottom: 8pt; }
.rule { border-top: 1px solid #1f4d46; margin: 4pt 0 6pt 0; }
.quote { margin-left: 14pt; font-style: italic; }
.auth { margin: 0 0 6pt 0; }
.meta { color: #555a61; font-size: 9.5pt; }
.link { color: #555a61; font-size: 8.5pt; }
.note { color: #6b6e75; font-size: 8.5pt; font-style: italic; margin-top: 14pt; }
"""


def _inline_html(text):
    out = ""
    for t, bold, italic in _runs(text):
        s = html.escape(t)
        if bold:
            s = f"<b>{s}</b>"
        if italic:
            s = f"<i>{s}</i>"
        out += s
    return out


def to_pdf(title, summary, authorities):
    body = [
        "<h1>Research Summary</h1>",
        f'<p class="sub">{html.escape(title)} &nbsp;·&nbsp; Prepared {_today()}</p>',
        '<div class="rule"></div>',
    ]
    for kind, payload in parse_blocks(summary):
        if kind == "h":
            body.append(f"<h2>{html.escape(_plain_cites(payload))}</h2>")
        elif kind == "p":
            body.append(f"<p>{_inline_html(payload)}</p>")
        elif kind in ("ul", "ol"):
            items = "".join(f"<li>{_inline_html(i)}</li>" for i in payload)
            body.append(f"<{kind}>{items}</{kind}>")
        elif kind == "quote":
            body.append(f'<p class="quote">{_inline_html(payload)}</p>')

    body.append("<h2>Authorities</h2>")
    for a in authorities:
        link = a.get("external_url")
        body.append(
            f'<p class="auth"><b>[{a["number"]}] {html.escape(a["case_title"])}</b><br>'
            f'<span class="meta">{html.escape(_authority_line(a))}</span>'
            + (f'<br><span class="link">{html.escape(link)}</span>' if link else "")
            + "</p>"
        )
    body.append(f'<p class="note">{html.escape(DISCLAIMER)}</p>')

    story = pymupdf.Story(html="".join(body), user_css=PDF_CSS)
    raw = io.BytesIO()
    writer = pymupdf.DocumentWriter(raw)
    page = pymupdf.paper_rect("a4")
    where = page + (54, 54, -54, -60)
    more = True
    while more:
        dev = writer.begin_page(page)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()

    # Page numbers
    doc = pymupdf.open("pdf", raw.getvalue())
    total = doc.page_count
    for i, pg in enumerate(doc, 1):
        pg.insert_textbox(
            pymupdf.Rect(0, page.height - 40, page.width, page.height - 24),
            f"Page {i} of {total}",
            fontsize=8.5, fontname="helv", color=(0.42, 0.43, 0.46), align=1,
        )
    doc.set_metadata({"title": f"Research Summary — {title}"})
    out = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return out
