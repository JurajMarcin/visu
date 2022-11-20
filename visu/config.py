from tomlconfig import configclass

@configclass
class Config:
    host: str = ""
    port: int = 8000
    debug: bool = False
    uvicorn_debug: bool = False
