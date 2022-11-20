import asyncio
import uvicorn
from . import config

config = uvicorn.Config(".:app", host=config.host, port=config.port,
                        log_level =
                        "debug" if config.uvicorn_debug else "info")
server = uvicorn.Server(config)
asyncio.run(server.serve())
