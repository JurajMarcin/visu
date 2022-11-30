from asyncio.futures import Future
import logging
from os import getpid
from random import randint
from time import time
from typing import Callable, Iterable
from bacpypes.apdu import (
    ConfirmedRequestSequence,
    SubscribeCOVRequest,
)
from bacpypes.core import deferred
from bacpypes.iocb import IOCB, IOController
from bacpypes.pdu import Address
from bacpypes.primitivedata import ObjectIdentifier
from bacpypes.task import OneShotTask
from fastapi.exceptions import HTTPException


_logger = logging.getLogger(__name__)


class _BaseRecurringTask(OneShotTask):
    def __init__(self, interval: int | None, offset: float | None = None) \
            -> None:
        self.interval = interval
        self.offset = offset
        self.cancelled = False
        super().__init__()
        _logger.debug("Init %r", self)

    def install_task(self, when: float | None = None,
                     delta: float | None = None) -> None:
        if self.cancelled:
            return
        offset = self.offset if self.offset is not None else 0
        super().install_task(when=time() + offset)

    def process_task(self) -> None:
        _logger.debug("Pocess task %r", self)
        if self.interval and not self.cancelled:
            super().install_task(delta=self.interval)

    def cancel_task(self) -> None:
        _logger.debug("Canceled task %r", self)
        self.cancelled = True


class _BaseIOTask(_BaseRecurringTask):
    def __init__(self, io_controller: IOController, interval: int,
                 offset: float | None = None,
                 callback: Callable[[IOCB], None] | None = None) -> None:
        if offset is None:
            offset = randint(0, interval * 1000 - 1) / 1000.0
        self.io_controller = io_controller
        self.callback = callback
        super().__init__(interval, offset)

    def _add_callback(self, iocb: IOCB) -> None:
        if self.callback is not None:
            iocb.add_callback(self.callback)

    def process_task(self) -> None:
        super().process_task()
        for request in self._build_requests():
            iocb = IOCB(request)
            self._add_callback(iocb)
            deferred(self.io_controller.request_io, iocb)

    def _build_requests(self) -> Iterable[ConfirmedRequestSequence]:
        raise NotImplementedError()


class SubscribeCOVTask(_BaseIOTask):
    def __init__(self, io_controller: IOController, address: Address,
                 object_identifier: ObjectIdentifier, cov_lifetime: int,
                 future: Future[bool]) \
            -> None:
        self.address = address
        self.object_identifier = object_identifier
        self.lifetime = cov_lifetime
        self.future = future
        super().__init__(io_controller, cov_lifetime, 0)

    def _build_requests(self) -> Iterable[ConfirmedRequestSequence]:
        yield SubscribeCOVRequest(
            destination=self.address,
            subscriberProcessIdentifier=getpid(),
            monitoredObjectIdentifier=self.object_identifier,
            issueConfirmedNotifications=False,
            lifetime=self.lifetime
        )

    def process_subscribe_ack(self, iocb: IOCB) -> None:
        if iocb.ioError:
            _logger.error("Failed to subscribe to %r@%r: %r",
                          self.object_identifier, self.address, iocb.ioError)
            if not self.future.done():
                self.future.set_exception(HTTPException(
                    500, f"Failed to subscribe to COV: {iocb.ioError}",
                ))
            self.cancel_task()
        else:
            _logger.debug("Subsribed to %r@%r", self.object_identifier,
                          self.address)
            if not self.future.done():
                self.future.set_result(True)

    def _add_callback(self, iocb: IOCB) -> None:
        iocb.add_callback(self.process_subscribe_ack)
