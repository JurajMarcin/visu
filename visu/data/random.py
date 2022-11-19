from logging import getLogger
from random import choice, randint, random
from time import time

from .base import COVCallback, DataModule

VALUE_TIMEOUT = 180

_logger = getLogger(__name__)


class RandomDataModule(DataModule):
    name = "random"

    def __init__(self) -> None:
        super().__init__()
        self.values: dict[str, tuple[float, str]] = dict()
        self.cov_requests: dict[str, dict[int, COVCallback]] = dict()
        self.running = False

    async def start(self) -> None:
        self.running = True

    async def stop(self) -> None:
        self.running = False

    async def get_value(self, data_id: str) -> str:
        _logger.debug("GET VALUE %r", data_id)
        if data_id in self.values \
                and time() + VALUE_TIMEOUT > self.values[data_id][0]:
            return self.values[data_id][1]
        if "int" in data_id:
            value = str(randint(0, 100))
        elif "float" in data_id:
            value = str(random())
        elif "bool" in data_id:
            value = str(choice([True, False]))
        else:
            value = choice(["Lorem", "Ipsum", "Dolor", "Sit", "Amet"])
        return value

    async def set_value(self, data_id: str, value: str) -> str | None:
        _logger.debug("GET VALUE %r=%r", data_id, value)
        self.values[data_id] = time(), value
        if id in self.cov_requests:
            await self.call_covs(data_id, value,
                                 self.cov_requests[data_id].values(), _logger)
        return value

    async def register_cov(self, data_id: str, callback_id: int,
                           callback: COVCallback) -> bool:
        if id not in self.cov_requests:
            self.cov_requests[data_id] = {}
        self.cov_requests[data_id][callback_id] = callback
        return True

    async def remove_cov(self, data_id: str, callback_id: int) -> None:
        if id in self.cov_requests \
                and callback_id in self.cov_requests[data_id]:
            del self.cov_requests[data_id][callback_id]
