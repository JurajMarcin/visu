import asyncio
from logging import Logger
from typing import Awaitable, Callable, Iterable

from tomlconfig import configclass


COVCallback = Callable[[str, str | list[str]], None | Awaitable[None]]


@configclass
class DataModuleConfig:
    pass


class DataModule:
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def get_value(self, data_id: str) -> str | list[str]:
        raise NotImplementedError(self.get_value.__qualname__)

    async def get_value_multiple(self, data_ids: Iterable[str]) \
            -> dict[str, str | list[str]]:
        return dict(zip(data_ids,
                        await asyncio.gather(*(self.get_value(data_id)
                                               for data_id in data_ids))))

    async def set_value(self, data_id: str, value: str) -> str | None:
        raise NotImplementedError(self.set_value.__qualname__)

    async def set_value_multiple(self,
                                 data_id_values: Iterable[tuple[str, str]]) \
            -> dict[str, str | None]:
        return dict(zip(
            map(lambda data_id_value: data_id_value[0], data_id_values),
            await asyncio.gather(*(self.set_value(data_id, value)
                                   for data_id, value in data_id_values)),
        ))

    async def register_cov(self, data_id: str, callback_id: int,
                           callback: COVCallback) -> bool:
        return False

    async def remove_cov(self, data_id: str, callback_id: int) -> None:
        pass

    @staticmethod
    async def call_covs(data_id: str, value: str | list[str],
                        callbacks: Iterable[COVCallback],
                        logger: Logger | None = None) -> None:
        for callback in callbacks:
            try:
                res = callback(data_id, value)
                if res is not None:
                    await res
            except Exception as ex:
                if logger is not None:
                    logger.warn("Exception while calling cov %r", ex)
