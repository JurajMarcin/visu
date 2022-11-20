from dataclasses import field
import logging
import re
from typing import Pattern
from fastapi.exceptions import HTTPException
from pymodbus.bit_read_message import ReadCoilsResponse, ReadDiscreteInputsResponse
from pymodbus.bit_write_message import WriteSingleCoilResponse
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient
from pymodbus.constants import Defaults
from pymodbus.exceptions import ModbusException
from pymodbus.framer.rtu_framer import ModbusRtuFramer
from pymodbus.framer.socket_framer import ModbusSocketFramer
from pymodbus.pdu import ExceptionResponse
from pymodbus.register_read_message import ReadHoldingRegistersResponse, ReadInputRegistersResponse
from pymodbus.register_write_message import WriteSingleRegisterResponse

from tomlconfig import configclass

from .base import DataModule, DataModuleConfig


_DATA_ID_RD_RE = re.compile(r"^(?P<conn_id>\w+)"
                            r"::(?P<slave>\d+)"
                            r"::(?P<obj_type>co|di|hr|ir):(?P<addr>\d+)"
                            r"(::?:(?P<count>\d+))?$")
_DATA_ID_WR_RE = re.compile(r"^(?P<conn_id>\w+)"
                            r"::(?P<slave>\d+)"
                            r"::(?P<obj_type>co|hr):(?P<addr>\d+)"
                            r"(::?:(?P<count>\d+))?$")
_logger = logging.getLogger(__name__)


@configclass
class ModbusConnectionSerial:
    port: str = ""
    ascii: bool = False
    baudrate: int = Defaults.Baudrate
    bytesize: int = Defaults.Bytesize
    parity: str = Defaults.Parity
    stopbits: int = Defaults.Stopbits


@configclass
class ModbusConnectionTCP:
    host: str = ""
    port: int = 502
    rtu: bool = False


@configclass
class ModbusConnection:
    conn_id: str = ""
    timout: int = Defaults.Timeout
    retries: int = Defaults.Retries
    tcp: ModbusConnectionTCP | None = None
    serial: ModbusConnectionSerial | None = None


@configclass
class ModbusDataModuleConfig(DataModuleConfig):
    conn: list[ModbusConnection] = field(default_factory=list)


def _build_client(config: ModbusConnection) \
        -> AsyncModbusTcpClient | AsyncModbusSerialClient:
    if config.tcp is not None:
        return AsyncModbusTcpClient(
            config.tcp.host,
            config.tcp.port,
            ModbusRtuFramer if config.tcp.rtu else ModbusSocketFramer,
            timeout=config.timout,
            retries=config.retries,
        )
    if config.serial is not None:
        return AsyncModbusSerialClient(
            config.serial.port,
            ModbusAsciiFramer if config.serial.ascii else ModbusRtuFramer,
            config.serial.baudrate,
            config.serial.bytesize,
            config.serial.parity,
            config.serial.stopbits,
            timeout=config.timout,
            retries=config.retries,
        )
    assert False


class ModbusDataModule(DataModule):
    name = "modbus"

    def __init__(self, config: ModbusDataModuleConfig) -> None:
        self._conns = { conn.conn_id: conn for conn in config.conn }

    def _parse_data_id(self, data_id: str, data_id_re: Pattern[str]) \
            -> tuple[str, int, str, int, int]:
        data = data_id_re.match(data_id)
        if data is None:
            raise HTTPException(400, "Invalid data id")
        count = data.group("count")
        return data.group("conn_id"), int(data.group("slave")), \
            data.group("obj_type"), int(data.group("addr")), \
            int(count) if count is not None else 1

    def _parse_data_id_read(self, data_id: str) \
            -> tuple[str, int, str, int, int]:
        return self._parse_data_id(data_id, _DATA_ID_RD_RE)

    def _parse_data_id_write(self, data_id: str) \
            -> tuple[str, int, str, int, int]:
        return self._parse_data_id(data_id, _DATA_ID_WR_RE)

    async def get_value(self, data_id: str) -> str | list[str]:
        client: AsyncModbusTcpClient | AsyncModbusSerialClient | None = None
        try:
            conn_id, slave, obj_type, addr, count = \
                self._parse_data_id_read(data_id)
            if conn_id not in self._conns:
                raise HTTPException(404, "Connection id not found")
            _logger.debug("Read from Modbus conn=%r slave=%r addr=%r count=%r",
                          conn_id, slave, addr, count)
            client = _build_client(self._conns[conn_id])
            await client.connect()
            res = await {
                "co": client.read_coils,
                "di": client.read_discrete_inputs,
                "hr": client.read_holding_registers,
                "ir": client.read_input_registers,
            }[obj_type](addr, count, slave)
            if isinstance(res, ExceptionResponse):
                raise HTTPException(500,
                                    f"Modbus error: {res} "
                                    f"code: {res.exception_code}")
            if isinstance(res, (ReadCoilsResponse,
                                ReadDiscreteInputsResponse)):
                value = res.bits
            elif isinstance(res, (ReadHoldingRegistersResponse,
                                  ReadInputRegistersResponse)):
                value = res.registers
            else:
                raise HTTPException(500, "Invalid response from Modbus")
            return list(map(str, value)) if count > 1 else str(value[0])
        except ModbusException as ex:
            raise HTTPException(500, f"Modbus exception: {ex}") from ex
        finally:
            if client is not None:
                await client.close()

    async def set_value(self, data_id: str, value: str) -> str | None:
        client: AsyncModbusTcpClient | AsyncModbusSerialClient | None = None
        try:
            conn_id, slave, obj_type, addr, count = \
                self._parse_data_id_write(data_id)
            if count != 1:
                raise HTTPException(400, "Cannot write multiple values")
            if conn_id not in self._conns:
                raise HTTPException(404, "Connection id not found")
            _logger.debug("Write from Modbus conn=%r slave=%r addr=%r value=%r",
                          conn_id, slave, addr, value)
            client = _build_client(self._conns[conn_id])
            await client.connect()
            if obj_type == "co":
                res = await client.write_coil(addr, bool(value), slave)
            elif obj_type == "hr":
                res = await client.write_register(addr, int(value), slave)
            else:
                assert False
            if isinstance(res, ExceptionResponse):
                raise HTTPException(500,
                                    f"Modbus error: {res} "
                                    f"code: {res.exception_code}")
            if isinstance(res, WriteSingleCoilResponse):
                return str(res.value)
            if isinstance(res, WriteSingleRegisterResponse):
                return str(res.value)
            raise HTTPException(500, "Invalid response from Modbus")
        except ValueError as ex:
            raise HTTPException(400, "Invalid value: {ex}") from ex
        finally:
            if client is not None:
                await client.close()
