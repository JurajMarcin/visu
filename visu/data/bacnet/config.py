from dataclasses import field

from bacpypes.pdu import Address

from tomlconfig import configclass

@configclass
class BacnetDataModuleConfig:
    device_name: str = "visu"
    device_identifier: int = 12
    address: Address = field(default_factory=Address)
    network_number: int = 2000
    max_apdu_length_accepted: int = 1024
    segmentation_supported: str = "segmentedBoth"
    vendor_identifier: int = 555
    cov_lifetime: int = 5 * 60
    timeout: int = 10
