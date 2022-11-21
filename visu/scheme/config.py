from dataclasses import field
from enum import Enum
import re

from tomlconfig import configclass


class ElementType(Enum):
    TEXT = 'text'
    INT = 'int'
    FLOAT = 'float'
    BOOL = 'bool'


@configclass
class ElementStyleConfig:
    match: str = ".*"
    min: float | None = None
    max: float | None = None

    fill: str | None = None
    opacity: float | None = None
    style: str | None = None
    text: str = "%%"

    def value_matches(self, value: str) -> bool:
        if self.min is not None or self.max is not None:
            try:
                num_value = float(value)
                if self.min is not None and num_value < self.min:
                    return False
                if self.max is not None and self.max < num_value:
                    return False
                return True
            except ValueError:
                pass
        return self.match is not None \
            and re.search(self.match, str(value)) is not None


@configclass
class ElementConfig:
    template: str | None = None
    data_module: str = ""
    data_id: str = ""
    svg_id: str = ""
    write: bool = False
    cov: bool = False
    single: bool = False
    influx_query: str = ""

    type: ElementType = ElementType.TEXT
    match: str | None = None
    min: float | None = None
    max: float | None = None

    map: dict[str, str] = field(default_factory=dict)
    precision: int = 4
    style: tuple[ElementStyleConfig, ...] = \
        field(default_factory=lambda: (ElementStyleConfig(),))


    def get_style_match(self, value: str) -> ElementStyleConfig | None:
        return next((style for style in self.style
                     if style.value_matches(value)), None)


@configclass
class SchemeConfig:
    scheme_name: str = ""
    scheme_id: str = ""
    svg_path: str = ""
    interval: int = 5
    element: list[ElementConfig] = field(default_factory=list)


@configclass
class SchemesConfig:
    scheme: list[SchemeConfig] = field(default_factory=list)
    template: list[ElementConfig] = field(default_factory=list)
