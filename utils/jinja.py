import os

from jinja2 import Environment, FileSystemLoader

from .dates import format_datetime, parse_datetime
from .text import slugify


def prepare_environment():
    """Create and configure a Jinja2 environment."""

    dirname = os.path.dirname(os.path.dirname(__file__))

    loader = FileSystemLoader(searchpath=os.path.join(dirname, "templates"))
    environment = Environment(loader=loader, autoescape=True)
    environment.filters["slugify"] = slugify
    environment.filters["parse_datetime"] = parse_datetime
    environment.filters["format_datetime"] = format_datetime
    environment.trim_blocks = True
    environment.lstrip_blocks = True

    return environment
