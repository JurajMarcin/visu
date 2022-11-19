from bacpypes.pdu import Address
from tomlconfig import configclass
from ..base import DataModuleConfig


@configclass
class BacnetDataModuleConfig(DataModuleConfig):
    object_name: str = "visubacnet"
    object_identifier: int = 400
    address: Address = Address("192.168.122.1/24")
    max_apdu_length_accepted: int = 1024
    segmentation_supported: str = "segmentedBoth"
    vendor_identifier: int = 15
    cov_lifetime: int = 5 * 60
    timeout: int = 10
