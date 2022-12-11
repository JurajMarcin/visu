from asyncio.futures import Future
from asyncio.queues import Queue
import logging
from os import getpid
from typing import Any

from bacpypes.apdu import (
    ConfirmedCOVNotificationRequest,
    ReadPropertyACK,
    ReadPropertyMultipleACK,
    SimpleAckPDU,
)
from bacpypes.app import BIPSimpleApplication
from bacpypes.constructeddata import Array
from bacpypes.iocb import IOCB
from bacpypes.local.device import LocalDeviceObject
from bacpypes.object import get_datatype
from bacpypes.pdu import Address
from bacpypes.primitivedata import ObjectIdentifier, Unsigned
from fastapi.exceptions import HTTPException

from .config import BacnetDataModuleConfig


_logger = logging.getLogger(__name__)


class VizuApplication(BIPSimpleApplication):
    def __init__(self, config: BacnetDataModuleConfig,
                 cov_queue: Queue[tuple[Address, ObjectIdentifier, str,
                                        str | list[str]]]):
        local_device = LocalDeviceObject(
            objectName=config.device_name,
            objectIdentifier=config.device_identifier,
            maxApduLengthAccepted=config.max_apdu_length_accepted,
            segmentationSupported=config.segmentation_supported,
            vendorIdentifier=config.vendor_identifier,
        )
        super().__init__(local_device, config.address)
        self.config = config
        self.cov_queue = cov_queue

    def process_read_property_ack(self, apdu: ReadPropertyACK,
                                  future: Future[str | list[str]]) -> None:
        datatype = get_datatype(apdu.objectIdentifier[0],
                                apdu.propertyIdentifier)
        if not datatype:
            _logger.error("unknown datatype in a response from %r",
                          apdu.pduSource)
            future.set_exception(HTTPException(500, "unknown datatype"))
            return

        if issubclass(datatype, Array) and apdu.propertyArrayIndex is not None:
            if apdu.propertyArrayIndex == 0:
                value = apdu.propertyValue.cast_out(Unsigned)
            else:
                value = apdu.propertyValue.cast_out(datatype.subtype)
        else:
            value = apdu.propertyValue.cast_out(datatype)

        future.set_result(list(map(str, value)) if isinstance(value, list)
                          else str(value))

    def process_read_property_multiple_ack(self, apdu: ReadPropertyMultipleACK,
                                           future: Future[dict[str, str
                                                               | list[str]]]) \
            -> None:
        results: dict[str, str | list[str]] = {}
        for result in apdu.listOfReadAccessResults:
            for element in result.listOfResults:
                if element.readResult.propertyAccessError is not None:
                    _logger.error("%r", element.readResult.propertyAccessError)
                    future.set_exception(HTTPException(
                        500, "Could not access property: "
                        f"{element.readResult.propertyAccessError}",
                    ))
                    return

                datatype = get_datatype(result.objectIdentifier[0],
                                        element.propertyIdentifier)
                if not datatype:
                    _logger.error("unknown datatype in a response from %r",
                                  apdu.pduSource)
                    future.set_exception(HTTPException(
                        500, "unknown datatype in a response",
                    ))
                    return

                if issubclass(datatype, Array) \
                        and element.propertyArrayIndex is not None:
                    if element.propertyArrayIndex == 0:
                        value = element.readResult.propertyValue.cast_out(
                            Unsigned)
                    else:
                        value = element.readResult.propertyValue.cast_out(
                            datatype.subtype)
                else:
                    value = element.readResult.propertyValue.cast_out(datatype)

                results[str(apdu.pduSource)
                        + "%%" + str(result.objectIdentifier[0])
                        + ":" + str(result.objectIdentifier[1])
                        + "%%" + str(element.propertyIdentifier)] = \
                    list(map(str, value)) if isinstance(value, list) \
                    else str(value)
        future.set_result(results)

    def process_response_iocb(self, iocb: IOCB, future: Future[Any],
                              **kwargs: Any) -> None:
        if iocb.ioError:
            _logger.error("%r", iocb.ioError)
            future.set_exception(HTTPException(500,
                                               f"Bacnet error {iocb.ioError}"))
            return
        if not iocb.ioResponse:
            _logger.error("No error nor response in IOCB response")
            future.set_exception(HTTPException(500, "No response nor error"))
            return

        apdu = iocb.ioResponse
        _logger.debug("Received %r from %r", type(apdu), apdu.pduSource)
        if isinstance(apdu, ReadPropertyACK):
            self.process_read_property_ack(apdu, future)
        elif isinstance(apdu, ReadPropertyMultipleACK):
            self.process_read_property_multiple_ack(apdu, future)
        elif isinstance(apdu, SimpleAckPDU):
            future.set_result(True)
        else:
            _logger.debug("Unhandled response type %r", type(apdu))
            future.set_result(None)

    def do_UnconfirmedCOVNotificationRequest(
            self, apdu: ConfirmedCOVNotificationRequest,
    ) -> None:
        _logger.debug("Received COV notification from %r", apdu.pduSource)
        if apdu.subscriberProcessIdentifier != getpid():
            _logger.debug("Ignoring COV notification not intended to me")
            return

        for element in apdu.listOfValues:
            value = element.value.tagList
            if len(value) == 1:
                value = value[0].app_to_object().value
            self.cov_queue.put_nowait((
                apdu.pduSource,
                ObjectIdentifier(apdu.monitoredObjectIdentifier),
                element.propertyIdentifier,
                list(map(str, value)) if isinstance(value, list)
                else str(value),
            ))
