import os
import time

from utils.models import BaseMetadata, DirectoryMetadata, LayoutConfig
from utils.text import slugify


def wait_ready(path: str):
    """Wait for a file to be fully created."""

    if not os.path.exists(path):
        return

    init_size = -1

    while True:
        current_size = os.path.getsize(path)
        if current_size == init_size:
            break

        init_size = current_size
        time.sleep(1)


def ensure_structure(layouts: list[LayoutConfig], base: str):
    """Ensure directory structure based on layout configuration."""

    for layout in layouts:
        dir_name = slugify(layout.name)
        dir_path = os.path.join(base, dir_name)

        os.makedirs(dir_path, exist_ok=True)

        if layout.content:
            ensure_structure(layout.content, dir_path)


def walk_layout(layouts: list[LayoutConfig], metadata: BaseMetadata | DirectoryMetadata, base: str = ""):
    """Walk through the layout structure and yield paths and metadata."""

    for layout in layouts:
        dir_name = slugify(layout.name)
        dir_path = os.path.join(base, dir_name)

        if dir_name not in metadata.content:
            metadata.content[dir_name] = DirectoryMetadata(
                slug=dir_name,
                name=layout.name,
                description=layout.description,
            )
        else:
            metadata.content[dir_name].slug = dir_name
            metadata.content[dir_name].name = layout.name
            metadata.content[dir_name].description = layout.description

        yield dir_path, metadata.content[dir_name]

        if layout.content:
            yield from walk_layout(layout.content, metadata.content[dir_name], dir_path)
