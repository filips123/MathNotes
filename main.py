import json
import logging
import os
import re
import shutil
import sys
import time
from urllib.parse import urljoin

import click
from pydantic_yaml import parse_yaml_file_as
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from utils.directories import ensure_structure, wait_ready, walk_layout
from utils.jinja import prepare_environment
from utils.models import BaseConfig, BaseMetadata, FileMetadata
from utils.pdf import set_pdf_metadata
from utils.repaginate import repaginate_pdf
from utils.samsung import extract_sdocx
from utils.text import slugify


class SourceHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith(".pdf"):
            wait_ready(event.src_path)

            config = parse_yaml_file_as(BaseConfig, self.config)

            run_pre_hook(config)
            handle_source(config)
            run_post_hook(config)


class TargetHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config

    def on_deleted(self, event):
        config = parse_yaml_file_as(BaseConfig, self.config)

        run_pre_hook(config)
        handle_target(config)
        run_post_hook(config)


class ConfigHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config

    def on_modified(self, event):
        if not event.is_directory and event.src_path == self.config:
            wait_ready(event.src_path)

            logging.info("Config file changed, reloading...")

            config = parse_yaml_file_as(BaseConfig, self.config)

            run_pre_hook(config)
            handle_source(config, False)
            handle_target(config, False)
            update_metadata(config, False)
            render_index(config)
            run_post_hook(config)


def handle_source(config: BaseConfig, index=True):
    ensure_structure(config.layouts, config.directories.source)
    ensure_structure(config.layouts, config.directories.target)

    metafile = os.path.join(config.directories.target, "metadata.json")

    if os.path.isfile(metafile):
        with open(metafile, encoding="utf-8") as file:
            metadata = BaseMetadata.model_validate_json(file.read())
    else:
        metadata = BaseMetadata(root={})

    changes = False

    for path, pathdata in walk_layout(config.layouts, metadata):
        source = os.path.join(config.directories.source, path)
        target = os.path.join(config.directories.target, path)

        for filename in os.listdir(source):
            if filename.lower().endswith(".pdf"):
                try:
                    name = re.sub(r" \(\d+\)$", "", filename[:-4])
                    parts = name.rsplit("_", 2)

                    title = parts[0]
                    slug = slugify(title)

                    source_filename = os.path.join(source, filename)
                    target_filename_pdf = os.path.join(target, slug + ".pdf")
                    target_filename_sdocx = os.path.join(target, slug + ".sdocx")

                    logging.info("Processing: %s", source_filename)

                    try:
                        modified = time.strptime(f"{parts[1]}-{parts[2]}", "%y%m%d-%H%M%S")
                    except (IndexError, ValueError):
                        logging.warning("Failed to parse date from filename, using file modification date")
                        modified = time.localtime(os.path.getmtime(os.path.join(source, filename)))

                    converted = time.localtime()

                    changes = True

                    if config.conversion.repaginate:
                        repaginate_pdf(
                            source_filename,
                            target_filename_pdf,
                            dpi=config.conversion.dpi,
                            height=config.conversion.height,
                        )

                        set_pdf_metadata(
                            filename=target_filename_pdf,
                            title=title,
                            author=config.meta.author,
                            language=config.meta.language,
                            modified=modified,
                            converted=converted,
                        )

                    else:
                        shutil.copy2(source_filename, target_filename_pdf)

                    sdocx = extract_sdocx(source_filename, target_filename_sdocx)

                    os.remove(source_filename)

                    pathdata.content[slug] = FileMetadata(
                        slug=slug,
                        name=title,
                        modified=time.strftime("%Y-%m-%d %H:%M:%S", modified),
                        converted=time.strftime("%Y-%m-%d %H:%M:%S", converted),
                        extensions=["pdf", "sdocx"] if sdocx else ["pdf"],
                    )

                    logging.info("Processed: %s", target_filename_pdf)

                except Exception as error:
                    logging.exception("Failed to process document: %s", error)

    if not changes:
        return

    logging.info("Saving metadata...")

    with open(metafile, "w", encoding="utf-8") as file:
        file.write(metadata.model_dump_json(indent=2) + "\n")

    if index:
        render_index(config)


def handle_target(config: BaseConfig, index=True):
    ensure_structure(config.layouts, config.directories.source)
    ensure_structure(config.layouts, config.directories.target)

    metafile = os.path.join(config.directories.target, "metadata.json")

    if os.path.isfile(metafile):
        with open(metafile, encoding="utf-8") as file:
            metadata = BaseMetadata.model_validate_json(file.read())
    else:
        metadata = BaseMetadata(root={})

    changes = False

    for path, pathdata in walk_layout(config.layouts, metadata):
        removed = []

        for slug, meta in pathdata.content.items():
            if not meta.type == "file":
                continue

            filename = os.path.join(config.directories.target, path, slug + ".pdf")

            if not os.path.isfile(filename):
                removed.append((slug, filename))

        for slug, filename in removed:
            logging.info("Removing: %s", filename)
            del pathdata.content[slug]
            changes = True

    if not changes:
        return

    logging.info("Saving metadata...")

    with open(metafile, "w", encoding="utf-8") as file:
        file.write(metadata.model_dump_json(indent=2) + "\n")

    if index:
        render_index(config)


def update_metadata(config: BaseConfig, index=True):
    metafile = os.path.join(config.directories.target, "metadata.json")

    if os.path.isfile(metafile):
        with open(metafile, encoding="utf-8") as file:
            metadata = BaseMetadata.model_validate_json(file.read())
    else:
        metadata = BaseMetadata(root={})

    for _ in walk_layout(config.layouts, metadata):
        # We don't need to do anything here, just iterate through the layout
        # Walking the layout already updates the metadata
        pass

    logging.info("Saving metadata...")

    with open(metafile, "w", encoding="utf-8") as file:
        file.write(metadata.model_dump_json(indent=2) + "\n")

    if index:
        render_index(config)


def sort_tree[T: dict](tree: T) -> T:
    if not isinstance(tree, dict):
        return tree

    # Sort directories first, then files, both alphabetically
    items = sorted(
        tree.items(),
        key=lambda item: (0 if item[1].type == "directory" else 1, item[1].name.lower()),
    )

    modified = {}

    for key, node in items:
        if getattr(node, "type", None) == "directory":
            node.content = sort_tree(node.content)
        modified[key] = node

    return modified


def render_index(config: BaseConfig):
    metafile = os.path.join(config.directories.target, "metadata.json")

    if not os.path.isfile(metafile):
        return

    logging.info("Rendering root index: index.html")

    with open(metafile, encoding="utf-8") as file:
        metadata = BaseMetadata.model_validate_json(file.read())

    environment = prepare_environment()
    template = environment.get_template("root.html")
    output = os.path.join(config.directories.target, "index.html")

    with open(output, "w", encoding="utf-8") as file:
        file.write(template.render(tree=sort_tree(metadata.content), meta=config.meta, index=config.index))

    render_subindexes(config)

    copy_assets(config)


def render_subindexes(config: BaseConfig):
    metafile = os.path.join(config.directories.target, "metadata.json")

    if not os.path.isfile(metafile):
        return

    with open(metafile, encoding="utf-8") as file:
        metadata = BaseMetadata.model_validate_json(file.read())

    environment = prepare_environment()
    template = environment.get_template("directory.html")

    def generate_subindexes(tree: dict, path: str = "", depth: int = 0, trail: list | None = None):
        if trail is None:
            trail = []

        for slug, node in tree.items():
            if node.type != "directory":
                continue

            node_path = os.path.join(path, slug)
            current_depth = depth + 1

            if config.index.depth != -1 and current_depth > config.index.depth:
                continue

            remaining_depth = -1 if config.index.depth == -1 else config.index.depth - current_depth

            index_dir = os.path.join(config.directories.target, node_path)
            os.makedirs(index_dir, exist_ok=True)

            index_path = os.path.join(index_dir, "index.html")

            index_url = urljoin(config.meta.base, node_path.replace(os.sep, "/"))
            if not index_url.endswith("/"):
                index_url += "/"

            breadcrumbs = [
                {"name": config.meta.title, "url": config.meta.base},
                *trail,
                {"name": node.name, "url": index_url},
            ]

            logging.info(
                "Rendering subindex: %s (depth=%d, remaining=%d)",
                os.path.relpath(index_path, config.directories.target),
                current_depth,
                remaining_depth,
            )

            with open(index_path, "w", encoding="utf-8") as file:
                file.write(
                    template.render(
                        tree=sort_tree(node.content),
                        name=node.name,
                        description=node.description,
                        meta=config.meta,
                        index=config.index,
                        current_depth=current_depth,
                        remaining_depth=remaining_depth,
                        canonical_url=index_url,
                        breadcrumbs=breadcrumbs,
                    )
                )

            if node.content:
                # Reconstruct trail separately to avoid problems with mutability
                new_trail = [*trail, {"name": node.name, "url": index_url}]
                generate_subindexes(node.content, node_path, current_depth, new_trail)

    generate_subindexes(metadata.content)

    if config.index.depth == -1:
        return

    # Cleanup indexes that are deeper than configured
    root = config.directories.target
    for dirpath, _, _ in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else len(rel.split(os.sep))
        if depth > config.index.depth:
            if os.path.isfile(os.path.join(dirpath, "index.html")):
                logging.info("Deleting subindex: %s", os.path.join(rel, "index.html"))
                os.remove(os.path.join(dirpath, "index.html"))


def copy_assets(config: BaseConfig):
    dirname = os.path.join(os.path.dirname(__file__))
    assets = os.path.join(dirname, "assets")
    target = os.path.join(dirname, config.directories.target)

    # Copy all assets to target directory
    shutil.copytree(assets, target, dirs_exist_ok=True)

    # Keep data and autogenerated files
    keep = {"index.html", "metadata.json"}

    # Add all top-level directories from config
    for layout in config.layouts:
        if hasattr(layout, "name"):
            keep.add(slugify(layout.name))

    def cleanup(current: str = "", toplevel: bool = False):
        for name in os.listdir(os.path.join(target, current)):
            if toplevel and name in keep:
                continue

            if os.path.isdir(os.path.join(target, current, name)):
                cleanup(os.path.join(current, name), toplevel=False)
                continue

            if os.path.isfile(os.path.join(assets, current, name)):
                continue

            logging.info("Deleting asset: %s", os.path.join(current, name))
            os.remove(os.path.join(target, current, name))

    # Cleanup excessive files in target
    if config.directories.cleanup:
        cleanup(toplevel=True)


def run_pre_hook(config: BaseConfig):
    if config.hooks.pre:
        logging.info("Running pre-hook: %s", config.hooks.pre)
        os.system(config.hooks.pre)


def run_post_hook(config: BaseConfig):
    if config.hooks.post:
        logging.info("Running post-hook: %s", config.hooks.post)
        os.system(config.hooks.post)


@click.group()
def cli():
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@cli.command()
def schema():
    """Print the JSON schema for the config."""

    schema = BaseConfig.model_json_schema()
    print(json.dumps(schema, indent=2))


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file.")
def process(config: str):
    """Process files once and exist."""

    config = parse_yaml_file_as(BaseConfig, config)

    run_pre_hook(config)
    handle_source(config, False)
    handle_target(config, False)
    update_metadata(config, False)
    render_index(config)
    run_post_hook(config)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file.")
def watch(config: str):
    """Process files and watch for changes."""

    configfile = os.path.abspath(config)

    config = parse_yaml_file_as(BaseConfig, configfile)

    run_pre_hook(config)
    handle_source(config, False)
    handle_target(config, False)
    update_metadata(config, False)
    render_index(config)
    run_post_hook(config)

    logging.info("Watching for file changes...")

    observer = Observer()
    observer.schedule(SourceHandler(configfile), config.directories.source, recursive=True)
    observer.schedule(TargetHandler(configfile), config.directories.target, recursive=True)
    observer.schedule(ConfigHandler(configfile), os.path.dirname(configfile), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    cli()
