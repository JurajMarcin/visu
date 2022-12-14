from logging import getLogger
from random import choice, randint, random
from time import time
from fastapi.exceptions import HTTPException

from .base import COVCallback, DataModule

VALUE_TIMEOUT = 180

_logger = getLogger(__name__)


class RandomDataModule(DataModule):
    name = "random"

    def __init__(self) -> None:
        super().__init__()
        self.values: dict[str, tuple[float, str]] = {}
        self.cov_requests: dict[str, dict[str, COVCallback]] = {}
        self.running = False

    async def start(self) -> None:
        _logger.debug("Random data module started")
        self.running = True

    async def stop(self) -> None:
        _logger.debug("Random data module stopped")
        self.running = False

    def _parse_data_id(self, data_id: str) -> tuple[str, str, float, float]:
        data = data_id.split("::")
        if len(data) < 1:
            raise HTTPException(400, "Invalid data id")
        try:
            return data[0], \
                data[1] if len(data) > 1 else "int", \
                float(data[2]) if len(data) > 2 else 0, \
                float(data[3]) if len(data) > 3 else 100
        except (TypeError, ValueError) as ex:
            raise HTTPException(400, "Invalid data id") from ex

    async def get_value(self, data_id: str) -> str:
        _logger.debug("get %r", data_id)
        name, data_type, value_min, value_max = self._parse_data_id(data_id)
        if name in self.values \
                and time() + VALUE_TIMEOUT > self.values[name][0]:
            return self.values[name][1]
        if data_type == "str":
            return choice(["Lorem", "Ipsum", "Dolor", "Sit", "Amet"])
        if data_type == "float":
            return str(random() * (value_max - value_min) + value_min)
        if data_type == "bool":
            return str(choice([True, False]))
        return str(randint(int(value_min), int(value_max)))

    async def set_value(self, data_id: str, value: str) -> str | None:
        _logger.debug("set %r=%r", data_id, value)
        name, _, _, _ = self._parse_data_id(data_id)
        self.values[name] = time(), value
        if name in self.cov_requests:
            await self.call_covs(data_id, value,
                                 self.cov_requests[name].values(), _logger)
        return value

    async def register_cov(self, data_id: str, callback_id: str,
                           callback: COVCallback) -> bool:
        _logger.debug("register_cov %r %r", data_id, callback_id)
        name, _, _, _ = self._parse_data_id(data_id)
        if name not in self.cov_requests:
            self.cov_requests[name] = {}
        self.cov_requests[name][callback_id] = callback
        return True

    async def remove_cov(self, data_id: str, callback_id: str) -> None:
        _logger.debug("remove_cov %r %r", data_id, callback_id)
        name, _, _, _ = self._parse_data_id(data_id)
        if name in self.cov_requests \
                and callback_id in self.cov_requests[name]:
            self.cov_requests[data_id].pop(callback_id)
