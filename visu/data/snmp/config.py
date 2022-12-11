from dataclasses import field
from enum import Enum

from pysnmp.hlapi.asyncio import (
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

from tomlconfig import configclass

@configclass
class SNMPCommunityConfig:
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
class SNMPUsmConfig:
    username: str = ""
    auth_key: str | None = None
    auth_key_file: str | None = None
    priv_key: str | None = None
    priv_key_file: str | None = None
    auth_protocol: SNMPAuthProtocol | None = None
    priv_protocol: SNMPPrivProtocol | None = None


@configclass
class SNMPConnectionConfig:
    conn_id: str = ""
    address: str = ""
    port: int = 161
    timeout: int = 1
    retries: int = 5
    ipv6: bool = False
    community_auth: SNMPCommunityConfig | None = None
    usm_auth: SNMPUsmConfig | None = None


@configclass
class SNMPDataModuleConfig:
    conn: list[SNMPConnectionConfig] = field(default_factory=list)
