from dataclasses import field
from enum import Enum

from tomlconfig import configclass


class ElementType(Enum):
    TEXT = 'text'
    INT = 'int'
    FLOAT = 'float'
    BOOL = 'bool'


@configclass
class TextElementConfig:
    enum: list[str] = field(default_factory=list)
    match: str | None = None

    map: dict[str, str] = field(default_factory=dict)


@configclass
class IntElementConfig:
    min: int | None = None
    max: int | None = None


@configclass
class FloatElementConfig:
    minf: float | None = None
    maxf: float | None = None

    precision: int = 4


@configclass
class BoolElementConfig:
    enum: list[str] = field(
        default_factory=lambda: ["true", "false", "True", "False", "0", "1"],
    )

    true_values: list[str] = \
        field(default_factory=lambda: ['true', 'True', '1'])
    true_text: str = ""
    false_text: str = ""
    true_fill: str = "#00AA00"
    false_fill: str = "#AA0000"


@configclass
class ElementConfig(TextElementConfig, IntElementConfig, FloatElementConfig,
                    BoolElementConfig):
    data_module: str = ""
    data_id: str = ""
    svg_id: str = ""
    write: bool = False
    type: ElementType = ElementType.TEXT
    cov: bool | None = None
    influx_query: str = ""


@configclass
class SchemeConfig:
    scheme_name: str = ""
    scheme_id: str = ""
    svg_path: str = ""
    elements: list[ElementConfig] = field(default_factory=list)
    interval: int = 5
    cov: bool = False


@configclass
class SchemesConfig:
    scheme: list[SchemeConfig] = field(default_factory=list)
