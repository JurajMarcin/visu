import asyncio
from pysnmp.hlapi.asyncio import getCmd, SnmpEngine, CommunityData, UdpTransportTarget, ContextData, ObjectType, ObjectIdentity


async def run(*args: ObjectType):
    iterator = getCmd(
        SnmpEngine(),
        CommunityData('public', mpModel=1),
        UdpTransportTarget(('localhost', 161)),
        ContextData(),
        *args,
    )
    return await iterator


asyncio.run(run())
