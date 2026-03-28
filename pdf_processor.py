import fitz  # PyMuPDF
from pathlib import Path


def convert_pdf_to_markdown(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    parts = []

    title = Path(pdf_path).stem.replace("-", " ").replace("_", " ").title()
    parts.append(f"# {title}\n")

    for page_num, page in enumerate(doc, 1):
        if len(doc) > 1:
            parts.append(f"\n---\n\n## Page {page_num}\n")

        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        font_sizes = _collect_font_sizes(blocks)
        heading_thresholds = _compute_heading_thresholds(font_sizes)

        prev_was_heading = False
        for block in blocks:
            if block["type"] == 1:
                parts.append("\n*[Image]*\n")
                prev_was_heading = False
                continue

            if block["type"] != 0:
                continue

            text, is_heading = _process_block(block, heading_thresholds)
            if not text:
                continue

            if is_heading and not prev_was_heading:
                parts.append("")
            parts.append(text)
            if is_heading:
                parts.append("")

            prev_was_heading = is_heading

    doc.close()
    return "\n".join(parts)


def _collect_font_sizes(blocks: list) -> list:
    sizes = []
    for block in blocks:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                if span["text"].strip():
                    sizes.append(round(span["size"], 1))
    return sizes


def _compute_heading_thresholds(font_sizes: list) -> dict:
    if not font_sizes:
        return {"h1": 999, "h2": 999, "h3": 999}

    body_size = _mode(font_sizes)
    unique_large = sorted(set(s for s in font_sizes if s > body_size * 1.1), reverse=True)

    h1 = unique_large[0] if len(unique_large) >= 1 else 999
    h2 = unique_large[1] if len(unique_large) >= 2 else 999
    h3 = unique_large[2] if len(unique_large) >= 3 else 999

    return {"h1": h1, "h2": h2, "h3": h3, "body": body_size}


def _mode(values: list):
    from collections import Counter
    return Counter(values).most_common(1)[0][0]


def _process_block(block: dict, thresholds: dict) -> tuple:
    lines_out = []
    block_sizes = []
    block_flags = []

    for line in block["lines"]:
        line_parts = []
        for span in line["spans"]:
            raw = span["text"]
            if not raw.strip():
                line_parts.append(raw)
                continue
            flags = span["flags"]
            size = round(span["size"], 1)
            block_sizes.append(size)
            block_flags.append(flags)

            is_bold = bool(flags & (1 << 4))
            is_italic = bool(flags & (1 << 1))

            text = raw
            if is_bold and is_italic:
                text = f"***{text.strip()}***"
            elif is_bold:
                text = f"**{text.strip()}**"
            elif is_italic:
                text = f"*{text.strip()}*"

            line_parts.append(text)

        joined = "".join(line_parts).strip()
        if joined:
            lines_out.append(joined)

    if not lines_out:
        return "", False

    full_text = " ".join(lines_out)

    # Detect list items
    stripped = full_text.lstrip()
    if stripped.startswith(("•", "·", "◦", "▪", "▸", "►", "✓", "✗")):
        return f"- {stripped[1:].strip()}", False
    if _is_numbered_list(stripped):
        return full_text, False

    # Heading detection
    avg_size = sum(block_sizes) / len(block_sizes) if block_sizes else 0

    if avg_size >= thresholds["h1"]:
        return f"# {_strip_formatting(full_text)}", True
    if avg_size >= thresholds["h2"]:
        return f"## {_strip_formatting(full_text)}", True
    if avg_size >= thresholds["h3"]:
        return f"### {_strip_formatting(full_text)}", True

    # Bold-only short line as heading fallback
    if block_flags and all(bool(f & (1 << 4)) for f in block_flags):
        body = thresholds.get("body", 0)
        if avg_size >= body and len(full_text) < 120:
            return f"#### {_strip_formatting(full_text)}", True

    return full_text, False


def _strip_formatting(text: str) -> str:
    return text.replace("***", "").replace("**", "").replace("*", "")


def _is_numbered_list(text: str) -> bool:
    import re
    return bool(re.match(r"^\d+[.)]\s", text))
