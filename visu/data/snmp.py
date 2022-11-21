from dataclasses import field
from enum import Enum
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
    usm3DESEDEPrivProtocol,
    usmAesCfb128Protocol,
    usmAesCfb192Protocol,
    usmAesCfb256Protocol,
    usmDESPrivProtocol,
    usmHMAC128SHA224AuthProtocol,
    usmHMAC192SHA256AuthProtocol,
    usmHMAC256SHA384AuthProtocol,
    usmHMAC384SHA512AuthProtocol,
    usmHMACMD5AuthProtocol,
    usmHMACSHAAuthProtocol,
    usmNoAuthProtocol,
    usmNoPrivProtocol,
)
from pysnmp.hlapi.auth import UsmUserData

from tomlconfig import ConfigError, configclass

from .base import DataModule, DataModuleConfig


_logger = logging.getLogger(__name__)


@configclass
class SNMPCommunity:
    community_name: str = ""
    version: int = 0


class SNMPAuthProtocol(Enum):
    NO = "no"
    HMACMD5 = "HMACMD5"
    HMACSHA = "HMACSHA"
    HMAC128SHA224 = "HMAC128SHA224"
    HMAC192SHA256 = "HMAC192SHA256"
    HMAC256SHA384 = "HMAC256SHA384"
    HMAC384SHA512 = "HMAC384SHA512"

    def get_oid(self) -> tuple[int, ...]:
        if self == SNMPAuthProtocol.NO:
            return usmNoAuthProtocol
        if self == SNMPAuthProtocol.HMACMD5:
            return usmHMACMD5AuthProtocol
        if self == SNMPAuthProtocol.HMACSHA:
            return usmHMACSHAAuthProtocol
        if self == SNMPAuthProtocol.HMAC128SHA224:
            return usmHMAC128SHA224AuthProtocol
        if self == SNMPAuthProtocol.HMAC192SHA256:
            return usmHMAC192SHA256AuthProtocol
        if self == SNMPAuthProtocol.HMAC256SHA384:
            return usmHMAC256SHA384AuthProtocol
        if self == SNMPAuthProtocol.HMAC384SHA512:
            return usmHMAC384SHA512AuthProtocol
        assert False


class SNMPPrivProtocol(Enum):
    NO = "no"
    DES = "DES"
    DESEDE = "3DESEDE"
    AESCFB128 = "AesCfb128"
    AESCFB192 = "AesCfb192"
    AESCFB256 = "AesCfb256"

    def get_oid(self) -> tuple[int, ...]:
        if self == SNMPPrivProtocol.NO:
            return usmNoPrivProtocol
        if self == SNMPPrivProtocol.DES:
            return usmDESPrivProtocol
        if self == SNMPPrivProtocol.DESEDE:
            return usm3DESEDEPrivProtocol
        if self == SNMPPrivProtocol.AESCFB128:
            return usmAesCfb128Protocol
        if self == SNMPPrivProtocol.AESCFB192:
            return usmAesCfb192Protocol
        if self == SNMPPrivProtocol.AESCFB256:
            return usmAesCfb256Protocol
        assert False



@configclass
class SNMPUsm:
    username: str = ""
    auth_key: str | None = None
    auth_key_file: str | None = None
    priv_key: str | None = None
    priv_key_file: str | None = None
    auth_protocol: SNMPAuthProtocol | None = None
    priv_protocol: SNMPPrivProtocol | None = None


@configclass
class SNMPConnection:
    conn_id: str = ""
    host: str = ""
    port: int = 161
    timeout: int = 1
    retries: int = 5
    ipv6: bool = False
    community_auth: SNMPCommunity | None = None
    usm_auth: SNMPUsm | None = None



@configclass
class SNMPDataModuleConfig(DataModuleConfig):
    conn: list[SNMPConnection] = field(default_factory=list)


class SNMPDataModule(DataModule):
    name = "snmp"

    def __init__(self, config: SNMPDataModuleConfig) -> None:
        self._conns = {}
        for conn in config.conn:
            if conn.conn_id in self._conns:
                raise ConfigError("Duplicate SNMP connection id: "
                                  f"{conn.conn_id}")
            self._conns[conn.conn_id] = conn

    def _parse_data_id(self, data_id: str) -> tuple[str, ObjectIdentity]:
        data = data_id.split("::")
        if len(data) < 2:
            raise HTTPException(400, "Invalid data id")
        return data[0], ObjectIdentity(*data[1:])

    def _get_auth_data(self, conn: SNMPConnection) \
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

    def _get_transport(self, conn: SNMPConnection) \
            -> UdpTransportTarget | Udp6TransportTarget:
        transport_type = Udp6TransportTarget if conn.ipv6 \
            else UdpTransportTarget
        return transport_type((conn.host, conn.port), conn.timeout,
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
