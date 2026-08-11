# app/export/pdf_exporter.py
import markdown
import weasyprint


def markdown_to_pdf(md_path: str) -> str:
    """Convert a Markdown file to PDF and return the PDF file path.

    Reads *md_path*, converts to HTML (with table support), then renders
    to PDF using WeasyPrint.  The PDF is written alongside the source file
    with the same name but a .pdf extension.

    Parameters
    ----------
    md_path:
        Path to the source .md file.

    Returns
    -------
    str
        Path to the written .pdf file.
    """
    with open(md_path, "r", encoding="utf-8") as fh:
        content = fh.read()

    html = markdown.markdown(content, extensions=["tables"])

    pdf_path = md_path.rsplit(".", 1)[0] + ".pdf"
    weasyprint.HTML(string=html).write_pdf(pdf_path)

    return pdf_path
