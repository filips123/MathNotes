from __future__ import annotations

import logging

import numpy as np
import pdfplumber
from PIL import Image


def combine_pages(
    filename: str,
    dpi: int | float = 300,
) -> Image:
    """Combine all pages of a PDF into a single image."""

    with pdfplumber.open(filename) as pdf:
        images = []

        width = 0
        height = 0

        for page in pdf.pages:
            image = page.to_image(resolution=dpi, antialias=True).original
            images.append(image)
            width = max(width, image.width)
            height += image.height

        combined = Image.new("RGB", (width, height), "white")
        position = 0

        for image in images:
            combined.paste(image, (0, position))
            position += image.height

    return combined


def find_possible_splits(
    image: Image,
    median_window: int = 10,
    median_threshold: int = 25050,
    split_height: int = 30,
    split_margin: int = 30,
) -> list[int]:
    """Find all possible horizontal splits in the image."""

    gray = image.convert("L")
    pixels = np.asarray(gray).astype("uint16") * 100
    lines = pixels.mean(axis=1)
    view = np.lib.stride_tricks.sliding_window_view(lines, (median_window,))
    medians = np.median(view, axis=1)

    splits = []

    split_start = None

    for position, median in enumerate(medians):
        if median >= median_threshold:
            if split_start is None:
                split_start = position

        else:
            if split_start is not None:
                if position - split_start >= split_height:
                    splits.append(max((split_start + position) // 2, position - split_margin))
                split_start = None

    if split_start is not None and len(medians) - split_start >= split_height:
        splits.append(split_start + split_margin)

    return splits


def find_optimal_splits(
    possible: list[int],
    page_height: int | float,
) -> list[int]:
    """Find the optimal splits based on the target page height."""

    splits = []

    current_start = 0
    current_end = 0

    for split in possible:
        if split - current_start <= page_height:
            current_end = split
        else:
            splits.append(current_end)
            current_start = split
            current_end = split

    return splits


def slice_image(
    image: Image,
    splits: list[int],
) -> list[Image]:
    """Slice the image into multiple images based on the provided splits."""

    width, height = image.size
    images = []

    position = 0

    for split in splits:
        box = (0, position, width, split)
        images.append(image.crop(box))
        position = split

    if position < height:
        box = (0, position, width, height)
        images.append(image.crop(box))

    return images


def export_pdf(
    images: list[Image],
    filename: str,
    dpi: int | float = 300,
):
    """Export images into a single PDF file."""

    images[0].save(
        filename,
        save_all=True,
        append_images=images[1:],
        resolution=dpi,
    )


def repaginate_pdf(
    input_filename: str,
    output_filename: str,
    dpi: int | float = 300,
    height: int | float = 297,
):
    """Repaginate a PDF file based on the target page height."""

    logging.info("Repaginating PDF")

    page_height_mm = height
    page_height_px = int(page_height_mm * dpi / 25.4)

    combined = combine_pages(input_filename, dpi=dpi)

    possible = find_possible_splits(combined)
    optimal = find_optimal_splits(possible, page_height_px)

    sliced = slice_image(combined, optimal)
    export_pdf(sliced, output_filename, dpi=dpi)
