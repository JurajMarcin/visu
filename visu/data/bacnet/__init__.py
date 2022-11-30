from asyncio import TimeoutError, wait_for
from asyncio.futures import Future
from asyncio.locks import Lock
from asyncio.queues import Queue
from asyncio.tasks import Task, create_task, gather
import logging
from threading import Thread
from typing import Iterable

from bacpypes.apdu import (
    ReadAccessSpecification,
    ReadPropertyMultipleRequest,
    ReadPropertyRequest,
    WritePropertyRequest,
)
from bacpypes.basetypes import PropertyReference
from bacpypes.constructeddata import Any, AnyAtomic
from bacpypes.core import deferred, run, stop
from bacpypes.iocb import IOCB
from bacpypes.object import get_datatype
from bacpypes.pdu import Address
from bacpypes.primitivedata import (
    Atomic,
    BitString,
    Boolean,
    CharacterString,
    Date,
    Double,
    Integer,
    Null,
    ObjectIdentifier,
    OctetString,
    Real,
    Time,
    Unsigned,
)
from fastapi.exceptions import HTTPException

from ..base import COVCallback, DataModule
from .app import VizuApplication
from .config import BacnetDataModuleConfig
from .tasks import SubscribeCOVTask


_logger = logging.getLogger(__name__)


class BacnetDataModule(DataModule):
    name = "bacnet"

    def __init__(self, config: BacnetDataModuleConfig) -> None:
        self.config = config
        self.cov_queue: Queue[tuple[Address, ObjectIdentifier, str,
                                    str | list[str]]] = Queue()
        self.cov_requests: dict[tuple[Address, ObjectIdentifier],
                                tuple[SubscribeCOVTask,
                                      dict[int, COVCallback]]] = {}
        self.cov_lock = Lock()
        self.cov_queue_task: Task[None] | None = None
        self.app = VizuApplication(config, self.cov_queue)
        self.thread: Thread = Thread(target=run)

    async def start(self) -> None:
        self.thread.start()
        self.cov_queue_task = create_task(self.cov_queue_mgr())

    async def stop(self) -> None:
        stop()
        if self.cov_queue_task is not None:
            self.cov_queue_task.cancel()

    async def cov_queue_mgr(self) -> None:
        while True:
            address, object_identifier, property_identifier, value = \
                await self.cov_queue.get()
            await self.cov_lock.acquire()
            try:
                data_id = (address, object_identifier)
                if data_id not in self.cov_requests:
                    return
                await DataModule.call_covs(
                    str(address) + "%%" + str(object_identifier.value[0]) + ":"
                    + str(object_identifier.value[1]) + "%%"
                    + str(property_identifier),
                    value, self.cov_requests[data_id][1].values(), _logger,
                )
            finally:
                self.cov_lock.release()

    async def get_value(self, data_id: str) -> str | list[str]:
        try:
            data = data_id.split("%%")
            address = Address(data[0])
            object_identifier = ObjectIdentifier(data[1])
            property_identifier = data[2]

            request = ReadPropertyRequest(
                destination=address,
                objectIdentifier=object_identifier,
                propertyIdentifier=property_identifier,
            )
            iocb = IOCB(request)
            future: Future[str | list[str]] = Future()
            iocb.add_callback(self.app.process_response_iocb, future)
            deferred(self.app.request_io, iocb)

            result = await wait_for(future, self.config.timeout)
            return result
        except (ValueError, KeyError, TypeError) as ex:
            raise HTTPException(400, "Invalid data_id") from ex
        except TimeoutError as ex:
            raise HTTPException(500, "Bacnet device timeout") from ex

    def _build_read_multiple_requests(self, data_ids: Iterable[str]) \
            -> Iterable[ReadPropertyMultipleRequest]:
        try:
            requests: dict[Address,
                           dict[ObjectIdentifier,
                                list[PropertyReference]]] = {}
            for data_id in data_ids:
                data = data_id.split("%%")
                address = Address(data[0])
                object_identifier = ObjectIdentifier(data[1])
                property_identifier = data[2]
                if address not in requests:
                    requests[address] = {}
                if object_identifier not in requests[address]:
                    requests[address][object_identifier] = []
                requests[address][object_identifier].append(
                    PropertyReference(propertyIdentifier=property_identifier),
                )

            return map(
                lambda address: ReadPropertyMultipleRequest(
                    destination=address,
                    listOfReadAccessSpecs=list(map(
                        lambda object_identifier: ReadAccessSpecification(
                            objectIdentifier=object_identifier,
                            listOfPropertyReferences=requests[address][object_identifier]
                        ),
                        requests[address],
                    )),
                ),
                requests,
            )
        except (ValueError, KeyError, TypeError) as ex:
            raise HTTPException(400, "Invalid data_id") from ex

    async def get_value_multiple(self, data_ids: Iterable[str]) \
            -> dict[str, str | list[str]]:
        try:
            futures: list[Future[dict[str, str | list[str]]]] = []
            for request in self._build_read_multiple_requests(data_ids):
                future: Future[dict[str, str | list[str]]] = Future()
                futures.append(future)
                iocb = IOCB(request)
                iocb.add_callback(self.app.process_response_iocb, future)
                deferred(self.app.request_io, iocb)
            results = await wait_for(gather(*futures), self.config.timeout)

            result: dict[str, str | list[str]] = {}
            for res in results:
                result.update(res)
            return result
        except TimeoutError as ex:
            raise HTTPException(500, "Bacnet device timeout") from ex

    async def set_value(self, data_id: str, value: str) -> str | None:
        try:
            data = data_id.split("%%")
            address = Address(data[0])
            object_identifier = ObjectIdentifier(data[1])
            property_identifier = data[2]
        except (ValueError, KeyError, TypeError) as ex:
            raise HTTPException(400, "Invalid data_id") from ex

        try:
            datatype = get_datatype(object_identifier.value[0],
                                    property_identifier)
            print(datatype)

            req_value = Any()
            if value == 'null':
                req_value.cast_in(Null())
            elif issubclass(datatype, AnyAtomic):
                dtype, dvalue = value.split(':', 1)
                datatype = {
                    'b': Boolean,
                    'u': lambda x: Unsigned(int(x)),
                    'i': lambda x: Integer(int(x)),
                    'r': lambda x: Real(float(x)),
                    'd': lambda x: Double(float(x)),
                    'o': OctetString,
                    'c': CharacterString,
                    'bs': BitString,
                    'date': Date,
                    'time': Time,
                    'id': ObjectIdentifier,
                }[dtype]
                req_value.cast_in(datatype(dvalue))
            elif issubclass(datatype, Atomic):
                if datatype is Integer:
                    parsed_value: int | float = int(value)
                elif datatype is Real:
                    parsed_value = float(value)
                elif datatype is Unsigned:
                    parsed_value = int(value)
                req_value.cast_in(datatype(parsed_value))
            else:
                raise HTTPException(400, "Could not determine datatype")
        except ValueError as ex:
            raise HTTPException(400, "Invalid value") from ex

        request = WritePropertyRequest(
            destination=address,
            objectIdentifier=object_identifier,
            propertyIdentifier=property_identifier,
            propertyValue=req_value,
        )
        iocb = IOCB(request)
        future: Future[str | list[str]] = Future()
        iocb.add_callback(self.app.process_response_iocb, future)
        deferred(self.app.request_io, iocb)

        try:
            result = await wait_for(future, self.config.timeout)
            return value if result else None
        except TimeoutError as ex:
            raise HTTPException(500, "Bacnet device timeout") from ex

    async def register_cov(self, data_id: str, callback_id: int,
                           callback: COVCallback) -> bool:
        try:
            data = data_id.split("%%")
            address = Address(data[0])
            object_identifier = ObjectIdentifier(data[1])
        except (ValueError, KeyError, TypeError) as ex:
            raise HTTPException(400, "Invalid data_id") from ex
        await self.cov_lock.acquire()
        try:
            did = (address, object_identifier)
            if data_id in self.cov_requests \
                    and not self.cov_requests[did][0].cancelled:
                self.cov_requests[did][1][callback_id] = callback
                return True
            future: Future[bool] = Future()
            task = SubscribeCOVTask(self.app, address, object_identifier,
                                    self.config.cov_lifetime, future)
            task.install_task()
            result = await wait_for(future, self.config.timeout)
            if not result:
                return False
            self.cov_requests[did] = (task, {callback_id: callback})
            return True
        except TimeoutError as ex:
            raise HTTPException(500, "Bacnet device timeout") from ex
        finally:
            self.cov_lock.release()

    async def remove_cov(self, data_id: str, callback_id: int) -> None:
        try:
            data = data_id.split("%%")
            address = Address(data[0])
            object_identifier = ObjectIdentifier(data[1])
        except (ValueError, KeyError, TypeError) as ex:
            raise HTTPException(400, "Invalid data_id") from ex
        await self.cov_lock.acquire()
        try:
            did = (address, object_identifier)
            if data_id not in self.cov_requests \
                    or callback_id not in self.cov_requests[did][1]:
                return
            del self.cov_requests[did][1][callback_id]
            if len(self.cov_requests[did][1]) == 0:
                self.cov_requests[did][0].cancel_task()
                del self.cov_requests[did]
        finally:
            self.cov_lock.release()
