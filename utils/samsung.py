import logging

from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import resolve1


def extract_sdocx(input_filename: str, output_filename: str) -> bool:
    """Extract a SDOCX file from the PDF file."""

    logging.info("Extracting SDOCX")

    with open(input_filename, "rb") as file:
        parser = PDFParser(file)
        document = PDFDocument(parser)

        if "PieceInfo" not in document.catalog:
            logging.warning("No Samsung Notes data detected")
            return False

        if "SPenSDK_PAGE_SINGLE" in document.catalog["PieceInfo"]:
            logging.info("Detected single page document")
            resolved = resolve1(document.catalog["PieceInfo"]["SPenSDK_PAGE_SINGLE"]["Private"]["Bin0"])
            data = resolved.get_data()

        elif "SPenSDK_PAGE_LIST" in document.catalog["PieceInfo"]:
            logging.info("Detected multi page document")
            resolved = resolve1(document.catalog["PieceInfo"]["SPenSDK_PAGE_LIST"]["Private"]["Bin0"])
            data = resolved.get_data()

        else:
            logging.warning("No Samsung Notes data detected")
            return False

    with open(output_filename, "wb") as file:
        file.write(data)

    return True
