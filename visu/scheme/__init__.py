"""Schemes module of the visu application"""
import asyncio
import logging
from typing import Iterable
from xml.etree import ElementTree as etree
from xml.etree.ElementTree import Element, ElementTree

from fastapi.exceptions import HTTPException

from tomlconfig import ConfigError, configclass_set_attrs, parse

from ..data import DataController
from .config import ElementConfig, ElementStyleConfig, ElementType, SchemeConfig, SchemesConfig


_logger = logging.getLogger(__name__)


class SchemesController:
    """Class for managing schemes"""
    def __init__(self) -> None:
        etree.register_namespace("", "http://www.w3.org/2000/svg")
        schemes_config = parse(SchemesConfig, "schemes.toml", "schemes.d")

        self._templates: dict[str, ElementConfig] = {}
        for template in schemes_config.template:
            if template.template is None:
                raise ConfigError("Template definition requires template name")
            if template.template in self._templates:
                raise ConfigError("Duplicate template name "
                                  f"{template.template}")
            self._templates[template.template] = template

        self._schemes: dict[str, SchemeConfig] = {}
        for scheme in schemes_config.scheme:
            if scheme.scheme_id in self._schemes:
                raise ConfigError(f"Duplicate scheme id {scheme.scheme_id}")
            self._schemes[scheme.scheme_id] = scheme

        self._resolve_templates()

    def _resolve_templates(self) -> None:
        for scheme in self._schemes.values():
            for element in scheme.element:
                if element.template is None:
                    continue
                if element.template not in self._templates:
                    raise ConfigError(f"Template '{element.template}' not "
                                      f"found, required by {element.svg_id} "
                                      f"in {scheme.scheme_id}")
                template = self._templates[element.template]
                explicit_attrs = configclass_set_attrs(element)
                for attr in configclass_set_attrs(template):
                    if attr not in explicit_attrs:
                        setattr(element, attr, getattr(template, attr))


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

    def get_element(self, scheme_id: str, svg_id: str) -> ElementConfig:
        """
        Returns an elemment with svg_id in the scheme with scheme_id

        Raises HTTPException(404) is either is not found
        """
        scheme = self.get_scheme(scheme_id)
        elements = list(filter(lambda el: el.svg_id == svg_id, scheme.element))
        if len(elements) != 1:
            raise HTTPException(404, "Element not found or duplicate svg_id")
        return elements[0]

    def _aggregate_elements(self, elements: Iterable[ElementConfig]) \
            -> dict[str, list[ElementConfig]]:
        aggregated: dict[str, list[ElementConfig]] = {}
        for element in elements:
            if element.data_module not in aggregated:
                aggregated[element.data_module] = []
            aggregated[element.data_module].append(element)
        return aggregated

    def _apply_style(self, svg_element: Element,
                     element_style: ElementStyleConfig, value: str) -> None:
        prev_style = svg_element.attrib.get("style", "")
        if element_style.fill is not None:
            svg_element.attrib["style"] = \
                f"{prev_style};fill:{element_style.fill}"
        if element_style.opacity is not None:
            svg_element.attrib["style"] = \
                f"{prev_style};opacity:{element_style.opacity}"
        if element_style.style is not None:
            svg_element.attrib["style"] = element_style.style
        if element_style.text is not None:
            for child in list(svg_element):
                svg_element.remove(child)
            svg_element.text = element_style.text.replace("%%", value)


    def _build_element(self, svg: ElementTree, element: ElementConfig,
                       data: str, scheme_id: str) -> None:
        svg_elements = svg.findall(f"//*[@id='{element.svg_id}']")
        if not svg_elements:
            _logger.error("Could not find '%r' in the SVG of scheme '%r'",
                          element.svg_id, scheme_id)
            return
        svg_element = svg_elements[0]

        element_style = element.get_style_match(data)
        if element_style is None:
            _logger.error("No style match for value '%r' in element %r in "
                          "scheme %r", data, element.svg_id, scheme_id)
            return
        if element.type == ElementType.FLOAT:
            try:
                data = f"{float(data):.{element.precision}}"
            except (TypeError, ValueError) as ex:
                _logger.error("Expected float value for %r in %r: %r",
                              element.svg_id, scheme_id, ex)
                return
        self._apply_style(svg_element, element_style,
                          element.map.get(data, data))

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
        aggr_elements = self._aggregate_elements(scheme.element)

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
                                    str(elements_data[element.data_id]),
                                    scheme_id)

        svg.getroot().attrib["width"] = "100%"
        svg.getroot().attrib["height"] = "100%"
        return etree.tostring(svg.getroot(), encoding="unicode")
