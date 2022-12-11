from dataclasses import field

from tomlconfig import configclass

from .data.bacnet.config import BacnetDataModuleConfig
from .data.modbus.config import ModbusDataModuleConfig
from .data.snmp.config import SNMPDataModuleConfig
from .scheme.config import (
    ElementConfig, ElementGroupTemplateConfig, SchemeConfig,
)


@configclass
class InfluxDdConfig:
    url: str = ""
    token: str = ""
    org: str = ""
    bucket: str = ""


@configclass
class Config:
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    uvicorn_debug: bool = False
    influx_db: InfluxDdConfig = field(default_factory=InfluxDdConfig)
    schemes_dir: str = "/etc/visu/schemes"

    bacnet: BacnetDataModuleConfig = \
        field(default_factory=BacnetDataModuleConfig)
    modbus: ModbusDataModuleConfig = \
        field(default_factory=ModbusDataModuleConfig)
    snmp: SNMPDataModuleConfig = field(default_factory=SNMPDataModuleConfig)

    scheme_element_template: list[ElementConfig] = field(default_factory=list)
    scheme_element_group: list[ElementGroupTemplateConfig] = \
        field(default_factory=list)
    scheme: list[SchemeConfig] = field(default_factory=list)
