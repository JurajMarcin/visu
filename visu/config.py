from tomlconfig import configclass

@configclass
class Config:
    host: str = ""
    port: int = 8000
    debug: bool = False
    uvicorn_debug: bool = False
    influxdb_url: str = ""
    influxdb_token: str = ""
    influxdb_org: str = ""
    influxdb_bucket: str = ""
