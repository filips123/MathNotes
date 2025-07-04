from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, RootModel


class HookConfig(BaseModel):
    pre: str | None = None
    post: str | None = None


class ConversionConfig(BaseModel):
    repaginate: bool = True
    dpi: int | float = 300
    height: int | float = 297


class DirectoriesConfig(BaseModel):
    source: str
    target: str


class LayoutConfig(BaseModel):
    name: str
    description: str = ""
    content: list[LayoutConfig] = []


class BaseConfig(BaseModel):
    hooks: HookConfig = Field(default_factory=HookConfig)
    conversion: ConversionConfig = Field(default_factory=ConversionConfig)
    directories: DirectoriesConfig
    layouts: list[LayoutConfig]


class DirectoryMetadata(BaseModel):
    type: Literal["directory"] = "directory"

    slug: str
    name: str
    description: str = ""

    content: AnyMetadata = Field(default_factory=dict)


class FileMetadata(BaseModel):
    type: Literal["file"] = "file"

    slug: str
    name: str
    description: str = ""

    modified: str | None = None
    converted: str | None = None

    extensions: list[str] = []


AnyMetadata = dict[str, DirectoryMetadata | FileMetadata]


class BaseMetadata(RootModel):
    root: AnyMetadata

    @property
    def content(self) -> AnyMetadata:
        return self.root

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]
