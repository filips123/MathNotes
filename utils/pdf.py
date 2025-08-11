import time

import pikepdf


def set_pdf_metadata(
    filename: str,
    title: str | None = None,
    description: str | None = None,
    subject: str | None = None,
    author: str | None = None,
    language: str | None = None,
    modified: time.struct_time | None = None,
    converted: time.struct_time | None = None,
):
    """Set metadata for a PDF file."""

    with pikepdf.Pdf.open(filename, allow_overwriting_input=True) as pdf:
        with pdf.open_metadata() as meta:
            if title is not None:
                meta["dc:title"] = title
            if description is not None:
                meta["dc:description"] = description
            if subject is not None:
                meta["dc:subject"] = [subject]
            if author is not None:
                meta["dc:creator"] = [author]
            if language is not None:
                meta["dc:language"] = [language]
            if modified is not None:
                meta["xmp:ModifyDate"] = time.strftime("%Y-%m-%dT%H:%M:%S", modified)
            if converted is not None:
                meta["xmp:MetadataDate"] = time.strftime("%Y-%m-%dT%H:%M:%S", converted)
            meta["xmp:CreatorTool"] = "MathNotes"
        pdf.save()
