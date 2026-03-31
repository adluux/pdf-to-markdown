import re
from collections import Counter
from pathlib import Path

import pypdf


def convert_pdf_to_markdown(pdf_path: str, title: str | None = None) -> str:
    reader = pypdf.PdfReader(pdf_path)
    pages = reader.pages

    all_spans = []
    page_spans = []

    for page in pages:
        spans = []

        def visitor(text, cm, tm, font_dict, font_size):
            if not text or not text.strip():
                return
            # Actual rendered size comes from the transform matrix
            size = abs(tm[3]) if tm and tm[3] else (font_size or 12)
            font_name = ""
            if font_dict:
                font_name = str(font_dict.get("/BaseFont", ""))
            spans.append({
                "text": text,
                "size": round(float(size), 1),
                "font": font_name,
                "x": tm[4] if tm else 0,
                "y": tm[5] if tm else 0,
            })

        page.extract_text(visitor_text=visitor)
        page_spans.append(spans)
        all_spans.extend(spans)

    body_size = _detect_body_size(all_spans)
    thresholds = _compute_thresholds(body_size)

    document_title = title or Path(pdf_path).stem
    document_title = document_title.replace("-", " ").replace("_", " ").strip().title()
    parts = [f"# {document_title}\n"]

    for page_num, spans in enumerate(page_spans, 1):
        if len(page_spans) > 1:
            parts.append(f"\n---\n\n## Page {page_num}\n")

        lines = _group_into_lines(spans)
        for line_spans in lines:
            md = _format_line(line_spans, thresholds, body_size)
            if md:
                parts.append(md)

    return "\n".join(parts)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_body_size(spans: list) -> float:
    sizes = [round(s["size"], 1) for s in spans if s["size"] > 0]
    if not sizes:
        return 11.0
    return Counter(sizes).most_common(1)[0][0]


def _compute_thresholds(body: float) -> dict:
    return {
        "h1": body * 1.8,
        "h2": body * 1.4,
        "h3": body * 1.15,
        "body": body,
    }


def _group_into_lines(spans: list) -> list:
    if not spans:
        return []
    sorted_spans = sorted(spans, key=lambda s: (-round(s["y"], 0), s["x"]))
    lines = []
    current = [sorted_spans[0]]
    for span in sorted_spans[1:]:
        if abs(span["y"] - current[-1]["y"]) < 3:
            current.append(span)
        else:
            lines.append(current)
            current = [span]
    lines.append(current)
    return lines


def _format_line(spans: list, thresholds: dict, body_size: float) -> str:
    if not spans:
        return ""

    sizes = [s["size"] for s in spans if s["size"] > 0]
    avg_size = sum(sizes) / len(sizes) if sizes else body_size

    text = " ".join(s["text"].strip() for s in spans if s["text"].strip())
    if not text:
        return ""

    # Detect bullet list
    stripped = text.lstrip()
    if stripped and stripped[0] in "•·◦▪▸►✓✗–—-" and len(stripped) > 2:
        return f"- {stripped[1:].strip()}"
    if re.match(r"^\d+[.)]\s", stripped):
        return text

    # Headings by size
    if avg_size >= thresholds["h1"]:
        return f"\n# {text}\n"
    if avg_size >= thresholds["h2"]:
        return f"\n## {text}\n"
    if avg_size >= thresholds["h3"]:
        return f"\n### {text}\n"

    # Bold font as subheading
    all_bold = spans and all(
        "bold" in s["font"].lower() or "heavy" in s["font"].lower()
        for s in spans if s["text"].strip()
    )
    if all_bold and len(text) < 120 and avg_size >= body_size:
        return f"\n#### {text}\n"

    # Inline bold/italic formatting
    parts = []
    for span in spans:
        t = span["text"].strip()
        if not t:
            continue
        font = span["font"].lower()
        bold = "bold" in font or "heavy" in font
        italic = "italic" in font or "oblique" in font
        if bold and italic:
            parts.append(f"***{t}***")
        elif bold:
            parts.append(f"**{t}**")
        elif italic:
            parts.append(f"*{t}*")
        else:
            parts.append(t)

    return " ".join(parts)
