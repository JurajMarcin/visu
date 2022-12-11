import logging

from fastapi.exceptions import HTTPException
from pysnmp.error import PySnmpError
from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    Udp6TransportTarget,
    UdpTransportTarget,
    getCmd,
    setCmd,
)
from pysnmp.hlapi.auth import UsmUserData

from tomlconfig import ConfigError

from ..base import DataModule
from .config import SNMPConnectionConfig, SNMPDataModuleConfig


_logger = logging.getLogger(__name__)


class SNMPDataModule(DataModule):
    name = "snmp"

    def __init__(self, config: SNMPDataModuleConfig) -> None:
        self._conns: dict[str, SNMPConnectionConfig] = {}
        for conn in config.conn:
            if conn.conn_id in self._conns:
                raise ConfigError("Duplicate SNMP connection id: "
                                  f"{conn.conn_id}")
            self._conns[conn.conn_id] = conn
        for conn in self._conns.values():
            if conn.usm_auth is not None:
                if conn.usm_auth.auth_key_file is not None:
                    with open(conn.usm_auth.auth_key_file, "r",
                              encoding="utf_8") as key_file:
                        conn.usm_auth.auth_key = key_file.read()
                if conn.usm_auth.priv_key_file is not None:
                    with open(conn.usm_auth.priv_key_file, "r",
                              encoding="utf_8") as key_file:
                        conn.usm_auth.auth_key = key_file.read()

    def _parse_data_id(self, data_id: str) -> tuple[str, ObjectIdentity]:
        data = data_id.split("::")
        if len(data) < 2:
            raise HTTPException(400, "Invalid data id")
        return data[0], ObjectIdentity(*data[1:])

    def _get_auth_data(self, conn: SNMPConnectionConfig) \
            -> CommunityData | UsmUserData:
        if conn.usm_auth:
            return UsmUserData(conn.usm_auth.username,
                               conn.usm_auth.auth_key,
                               conn.usm_auth.priv_key,
                               conn.usm_auth.auth_protocol.get_oid()
                               if conn.usm_auth.auth_protocol is not None
                               else None,
                               conn.usm_auth.priv_protocol.get_oid()
                               if conn.usm_auth.priv_protocol is not None
                               else None)
        if conn.community_auth is not None:
            return CommunityData(conn.community_auth.community_name,
                                 mpModel=conn.community_auth.version)
        return CommunityData("public", mpModel=1)

    def _get_transport(self, conn: SNMPConnectionConfig) \
            -> UdpTransportTarget | Udp6TransportTarget:
        transport_type = Udp6TransportTarget if conn.ipv6 \
            else UdpTransportTarget
        return transport_type((conn.address, conn.port), conn.timeout,
                              conn.retries)

    async def get_value(self, data_id: str) -> str | list[str]:
        conn_id, obj_id = self._parse_data_id(data_id)
        if conn_id not in self._conns:
            raise HTTPException(404, "SNMP connection not found")

        _logger.debug("SNMP get conn=%r object=%r", conn_id, obj_id)
        try:
            engine_error, pdu_error, _, results = await getCmd(
                SnmpEngine(),
                self._get_auth_data(self._conns[conn_id]),
                self._get_transport(self._conns[conn_id]),
                ContextData(),
                ObjectType(obj_id),
            )
            if engine_error:
                raise HTTPException(500, f"SNMP Engine error: {engine_error}")
            if pdu_error:
                raise HTTPException(500, f"SNMP Pdu error: {pdu_error}")
            if len(results) == 1:
                return results[0][1].prettyPrint()
            return list(map(lambda result: result[1].prettyPrint(), results))
        except PySnmpError as ex:
            raise HTTPException(500, f"SNMP error: {ex}") from ex

    async def set_value(self, data_id: str, value: str) -> str | None:
        conn_id, obj_id = self._parse_data_id(data_id)
        if conn_id not in self._conns:
            raise HTTPException(404, "SNMP connection not found")

        _logger.debug("set conn=%r object=%r value=%r", conn_id, obj_id,
                      value)
        try:
            engine_error, pdu_error, _, results = await setCmd(
                SnmpEngine(),
                self._get_auth_data(self._conns[conn_id]),
                self._get_transport(self._conns[conn_id]),
                ContextData(),
                ObjectType(obj_id, value),
            )
            if engine_error:
                _logger.error("Engine Error: %r", engine_error)
                raise HTTPException(500, f"SNMP Engine error: {engine_error}")
            if pdu_error:
                _logger.error("Pdu Error: %r", pdu_error)
                raise HTTPException(500, f"SNMP Pdu error: {pdu_error}")
            return results[0][1].prettyPrint()
        except PySnmpError as ex:
            _logger.error("Error: %r", ex)
            raise HTTPException(500, f"SNMP error: {ex}") from ex
