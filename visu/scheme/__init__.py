"""Schemes module of the visu application"""
import asyncio
import logging
import re
from typing import Iterable
from xml.etree import ElementTree as etree
from xml.etree.ElementTree import ElementTree

from fastapi.exceptions import HTTPException

from tomlconfig import ConfigError, parse

from ..data import DataController
from .config import ElementConfig, ElementType, SchemeConfig, SchemesConfig


_logger = logging.getLogger(__name__)


class SchemesController:
    """Class for managing schemes"""
    def __init__(self) -> None:
        etree.register_namespace("", "http://www.w3.org/2000/svg")
        self._schemes: dict[str, SchemeConfig] = {}
        for scheme in parse(SchemesConfig, "schemes.toml", "schemes.d").scheme:
            if scheme.scheme_id in self._schemes:
                raise ConfigError(f"Duplicate scheme id {scheme.scheme_id}")
            self._schemes[scheme.scheme_id] = scheme

    def get_schemes(self) -> Iterable[SchemeConfig]:
        """Returns a list of configured schemes"""
        return self._schemes.values()

    def get_scheme(self, scheme_id: str) -> SchemeConfig:
        """
        Returns a scheme with scheme_id.

        Raises HTTPException(404) if scheme_id is not found.
        """
        if scheme_id not in self._schemes:
            raise HTTPException(404, "Scheme not found")
        return self._schemes[scheme_id]

    def _aggregate_elements(self, elements: Iterable[ElementConfig]) \
            -> dict[str, list[ElementConfig]]:
        aggregated: dict[str, list[ElementConfig]] = {}
        for element in elements:
            if element.data_module not in aggregated:
                aggregated[element.data_module] = []
            aggregated[element.data_module].append(element)
        return aggregated

    def _build_element(self, svg: ElementTree, element: ElementConfig,
                       data: str | list[str], scheme_id: str) -> None:
        svg_elements = svg.findall(f"//*[@id='{element.svg_id}']")
        if not svg_elements:
            _logger.error("Could not find '%r' in the svg xml of scheme '%r'",
                          element.svg_id, scheme_id)
        svg_element = svg_elements[0]

        match element.type:
            case ElementType.TEXT:
                svg_element.text = str(
                    element.map.get(data, data) if isinstance(data, str) \
                    else list(map(lambda d: element.map.get(d, d), data))
                )
            case ElementType.INT:
                svg_element.text = str(data)
            case ElementType.FLOAT:
                svg_element.text = str(
                    f"{float(data):.{element.precision}f}" \
                    if isinstance(data, str) else \
                    list(map(lambda d: f"{float(d):.{element.precision}f}",
                             data))
                )
            case ElementType.BOOL:
                value = data in element.true_values
                svg_element.text = element.true_text if value \
                    else element.false_text
                if "style" in svg_element.attrib:
                    style = svg_element.attrib["style"]
                    fill = element.true_fill if value else element.false_fill
                    svg_element.attrib["style"] = re.sub(r"fill:[^;]+",
                                                         f"fill:{fill}",
                                                         style, 0)

        for child in list(svg_element):
            svg_element.remove(child)

    async def build_svg(self, scheme_id: str,
                         data_controller: DataController) -> str:
        """
        Builds the final SVG of scheme with scheme_id SVG XML using values
        retrieved from data_controller.

        Raises:
        - HTTPException(404) if the scheme_id is not found
        - HTTPException(500) if the scheme svg file could not be loaded
        """
        if scheme_id not in self._schemes:
            raise HTTPException(404, "Scheme not found")
        scheme = self._schemes[scheme_id]
        try:
            svg = etree.parse(f"./schemes/{scheme.svg_path}")
        except OSError as ex:
            raise HTTPException(500, "Could not load scheme SVG") from ex
        aggr_elements = self._aggregate_elements(scheme.elements)

        data_tasks = map(lambda data_module: \
                            data_controller.get_values(data_module, map(
                                lambda element: element.data_id,
                                aggr_elements[data_module],
                            )),
                         aggr_elements.keys())

        data = await asyncio.gather(*data_tasks)
        for elements, elements_data in zip(aggr_elements.values(), data):
            for element in elements:
                self._build_element(svg, element,
                                    elements_data[element.data_id], scheme_id)

        svg.getroot().attrib["width"] = "100%"
        svg.getroot().attrib["height"] = "100%"
        return etree.tostring(svg.getroot(), encoding="unicode")
