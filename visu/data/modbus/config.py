from dataclasses import field

from pymodbus.constants import Defaults

from tomlconfig import configclass

@configclass
class ModbusConnectionSerialConfig:
    port: str = ""
    ascii: bool = False
    baudrate: int = Defaults.Baudrate
    bytesize: int = Defaults.Bytesize
    parity: str = Defaults.Parity
    stopbits: int = Defaults.Stopbits
    handle_local_echo: bool = Defaults.HandleLocalEcho


@configclass
class ModbusConnectionTCPConfig:
    address: str = ""
    port: int = 502
    rtu: bool = False


@configclass
class ModbusConnectionConfig:
    conn_id: str = ""
    timout: int = Defaults.Timeout
    retries: int = Defaults.Retries
    tcp: ModbusConnectionTCPConfig | None = None
    serial: ModbusConnectionSerialConfig | None = None


@configclass
class ModbusDataModuleConfig:
    conn: list[ModbusConnectionConfig] = field(default_factory=list)
