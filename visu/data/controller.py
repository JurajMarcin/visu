from typing import Iterable

from fastapi.exceptions import HTTPException

from ..config import Config
from .bacnet.module import BacnetDataModule
from .base import COVCallback, DataModule
from .modbus.module import ModbusDataModule
from .random import RandomDataModule
from .snmp.module import SNMPDataModule


class DataController:
    def __init__(self, config: Config) -> None:
        self.data_modules: dict[str, DataModule] = {
            RandomDataModule.name: RandomDataModule(),
            BacnetDataModule.name: BacnetDataModule(config.bacnet),
            ModbusDataModule.name: ModbusDataModule(config.modbus),
            SNMPDataModule.name: SNMPDataModule(config.snmp)
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

    async def register_cov(self, module: str, data_id: str, callback_id: str,
                           callback: COVCallback) -> bool:
        if not module or module not in self.data_modules:
            raise HTTPException(404, "Data module not found")
        return await self.data_modules[module].register_cov(data_id,
                                                            callback_id,
                                                            callback)

    async def remove_cov(self, module: str, data_id: str, callback_id: str) \
            -> None:
        if not module or module not in self.data_modules:
            raise HTTPException(404, "Data module not found")
        return await self.data_modules[module].remove_cov(data_id, callback_id)
