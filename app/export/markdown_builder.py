# app/export/markdown_builder.py
import os
import re
from datetime import datetime


def _fix_reference_spacing(report: str) -> str:
    """Ensure each [N] reference entry in the References section starts on its
    own paragraph by inserting a blank line before any [N] marker that isn't
    already preceded by one.

    Only lines within the ## References section are touched; inline [N]
    citations in the body are left untouched because the regex only operates
    on the substring after the References heading.
    """
    # Split at the References heading (case-insensitive, various heading levels)
    split_re = re.compile(r"(#{1,6}\s*References\b.*)", re.IGNORECASE)
    parts = split_re.split(report, maxsplit=1)

    if len(parts) < 3:
        # No References section found — return unchanged
        return report

    body, ref_heading, ref_section = parts[0], parts[1], parts[2]

    # Insert a blank line before each [N] marker that isn't already preceded
    # by a blank line.  The pattern matches a single newline (not \n\n) before
    # a [N] entry and replaces it with two newlines (blank line separator).
    ref_section = re.sub(r"(?<!\n)\n(\[\d+\])", r"\n\n\1", ref_section)

    return body + ref_heading + ref_section


def _slugify(text: str) -> str:
    """Convert *text* to a lowercase, hyphen-separated filename-safe slug."""
    text = text.lower().strip()
    # Replace any run of non-alphanumeric characters with a single hyphen
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Strip leading/trailing hyphens
    return text.strip("-")


def save_markdown(report: str, topic: str, output_dir: str = "reports") -> str:
    """Write *report* to a timestamped Markdown file and return the file path.

    Parameters
    ----------
    report:
        Full report content in Markdown.
    topic:
        Original research topic — used to derive the filename slug.
    output_dir:
        Directory to write into. Created if it doesn't exist.

    Returns
    -------
    str
        Absolute path to the written .md file.
    """
    os.makedirs(output_dir, exist_ok=True)

    slug = _slugify(topic)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{slug}-{timestamp}.md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(_fix_reference_spacing(report))

    return os.path.abspath(filepath)
