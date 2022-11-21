from typing import Iterable

from fastapi.exceptions import HTTPException
from tomlconfig import parse
from visu.data.snmp import SNMPDataModule, SNMPDataModuleConfig

from .bacnet import BacnetDataModule, BacnetDataModuleConfig
from .modbus import ModbusDataModule, ModbusDataModuleConfig
from .base import COVCallback, DataModule
from .random import RandomDataModule


class DataController:
    def __init__(self) -> None:
        self.data_modules: dict[str, DataModule] = {
            RandomDataModule.name: RandomDataModule(),
            BacnetDataModule.name: BacnetDataModule(BacnetDataModuleConfig()),
            ModbusDataModule.name: ModbusDataModule(
                parse(ModbusDataModuleConfig, "modbus.toml"),
            ),
            SNMPDataModule.name: SNMPDataModule(parse(SNMPDataModuleConfig,
                                                      "snmp.toml"))
        }

    async def start(self) -> None:
        for _, data_module in self.data_modules.items():
            await data_module.start()

    async def stop(self) -> None:
        for _, data_module in self.data_modules.items():
            await data_module.stop()

    async def get_values(self, data_module: str, data_ids: Iterable[str]) \
            -> dict[str, str | list[str]]:
        if data_module not in self.data_modules:
            raise HTTPException(404, "Data module not found")
        data_ids = list(data_ids)
        if len(data_ids) == 1:
            return {
                data_ids[0]: await self.data_modules[data_module]
                    .get_value(data_ids[0]),
            }
        return await self.data_modules[data_module] \
            .get_value_multiple(data_ids)

    async def set_values(self, data_module: str, data: dict[str, str]) \
            -> dict[str, str | None]:
        if data_module not in self.data_modules:
            raise HTTPException(404, "Data module not found")
        if len(data) == 1:
            data_id, value = list(data.items())[0]
            return {
                data_id: await self.data_modules[data_module]
                    .set_value(data_id, value),
            }
        return await self.data_modules[data_module] \
            .set_value_multiple(data.items())

    async def register_cov(self, module: str, data_id: str, callback_id: int,
                           callback: COVCallback) -> bool:
        if not module or module not in self.data_modules:
            raise HTTPException(404, "Data module not found")
        return await self.data_modules[module].register_cov(data_id,
                                                            callback_id,
                                                            callback)

    async def remove_cov(self, module: str, data_id: str, callback_id: int) \
            -> None:
        if not module or module not in self.data_modules:
            raise HTTPException(404, "Data module not found")
        return await self.data_modules[module].remove_cov(data_id, callback_id)
