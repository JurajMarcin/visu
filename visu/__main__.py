import asyncio
import uvicorn
from . import visu_config

print("PORT", visu_config.port)
uvicorn_config = uvicorn.Config(
    "visu:app",
    host=visu_config.host,
    port=visu_config.port,
    log_level="debug" if visu_config.uvicorn_debug else "info",
)
server = uvicorn.Server(uvicorn_config)
asyncio.run(server.serve())
