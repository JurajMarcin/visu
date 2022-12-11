from argparse import ArgumentParser
import asyncio
from dataclasses import dataclass, field
import logging
from os.path import dirname, isdir
from secrets import token_urlsafe
from sys import stderr
from typing import cast

from aiohttp.client_exceptions import ClientError
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.encoders import jsonable_encoder
from fastapi.params import Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from starlette.requests import Request
from starlette.responses import Response
from starlette.websockets import WebSocketDisconnect
from tomlconfig import ConfigError, parse
import uvicorn

from .config import Config
from .data.controller import DataController
from .scheme.controller import SchemesController

_logger = logging.getLogger(__name__)

parser = ArgumentParser("Visu")
parser.add_argument("--debug", help="show debug output on stderr",
                    action="store_true", default=False)
parser.add_argument("--config",
                    help="load config from the file CONFIG or load config "
                    "from files in the directory CONFIG in alphabetical "
                    "order")
args = parser.parse_args()

if args.config is None:
    visu_config = parse(Config, conf_d_path=args.config)
else:
    try:
        visu_config = parse(Config, conf_d_path=args.config) \
            if isdir(args.config) else parse(Config, conf_path=args.config)
    except FileNotFoundError as ex:
        raise ConfigError("No configuration!") from ex
if args.debug:
    visu_config.debug = True

log_handler = logging.StreamHandler(stderr)
log_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"),
)
_logger.addHandler(log_handler)
_logger.setLevel(logging.DEBUG if visu_config.debug else logging.INFO)


data_controller = DataController(visu_config)
schemes_controller = SchemesController(visu_config)

app = FastAPI()
app.mount("/static", StaticFiles(directory=f"{dirname(__file__)}/static"),
          name="static")
templates = Jinja2Templates(f"{dirname(__file__)}/templates/")


@app.on_event("startup")
async def startup_event() -> None:
    await data_controller.start()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await data_controller.stop()


@app.get("/data/{module}")
async def get_data(module: str,
                   data_id: list[str] | None = cast(None, Query(None))) \
        -> dict[str, str | list[str]]:
    if data_id is None or len(data_id) == 0:
        raise HTTPException(400, "No id to get")
    return await data_controller.get_values(module, data_id)


@app.post("/data/{module}")
async def set_data(module: str, data: dict[str, str]) \
        -> dict[str, str | None]:
    if len(data) == 0:
        raise HTTPException(400, "No data to set")
    return await data_controller.set_values(module, data)


@dataclass
class WSMessage:
    command: str = ""
    data_ids: list[str] = field(default_factory=list)
    data: dict[str, str] = field(default_factory=dict)


@app.websocket("/ws/{module}")
async def data_websocket(websocket: WebSocket, module: str) -> None:
    await websocket.accept()
    callbacks: list[tuple[str, str]] = []
    try:
        while True:
            data = await websocket.receive_json()
            try:
                message = WSMessage(**data)
                if message.command == "get":
                    await websocket.send_json(
                        await data_controller.get_values(module,
                                                         message.data_ids),
                    )
                elif message.command == "set":
                    await websocket.send_json(
                        await data_controller.set_values(module, message.data),
                    )
                elif message.command == "cov":
                    for data_id in message.data_ids:
                        callback_id = token_urlsafe(16)
                        async def callback(data_id: str,
                                           value: str | list[str]) -> None:
                            await websocket.send_json({data_id: value})
                        callbacks.append((data_id, callback_id))
                        if await data_controller.register_cov(module, data_id,
                                                              callback_id,
                                                              callback):
                            await websocket.send_json({
                                "status": 200,
                                "detail": "Subsribed",
                            })
                        else:
                            await websocket.send_json({
                                "status": 403,
                                "detail": "Module does not support COV messages",
                            })
                else:
                    await websocket.send_json({
                        "status": 400,
                        "detail": f"Invalid command '{message.command}'",
                    })
            except HTTPException as ex:
                await websocket.send_json({
                    "status": ex.status_code,
                    "detail": ex.detail,
                })
            except TypeError:
                await websocket.send_json({
                    "status": 400,
                    "detail": "Invalid message",
                })
    except WebSocketDisconnect:
        pass
    finally:
        for data_id, callback_id in callbacks:
            await data_controller.remove_cov(module, data_id, callback_id)


@app.get("/")
async def get_index(request: Request) -> Response:
    return templates.TemplateResponse("index.html", {
        "request": request,
        "schemes": schemes_controller.get_schemes(),
    })


@app.get("/schemes/{scheme_id}")
async def get_scheme(request: Request, scheme_id: str) -> Response:
    scheme_config = schemes_controller.get_scheme(scheme_id)
    return templates.TemplateResponse("scheme.html", {
        "request": request,
        "svg": await schemes_controller.build_svg(scheme_id, data_controller),
        "scheme_config": jsonable_encoder(scheme_config),
        "schemes": schemes_controller.get_schemes(),
        "scheme_name": scheme_config.scheme_name,
    })


@app.get("/schemes/{scheme_id}/influx/{svg_id}")
async def get_influx_data(scheme_id: str, svg_id: str, limit: str = "-1h") \
        -> Response:
    element = schemes_controller.get_element(scheme_id, svg_id)
    try:
        async with InfluxDBClientAsync(visu_config.influx_db.url,
                                       visu_config.influx_db.token,
                                       visu_config.influx_db.org) as client:
            await client.ping()
            query = client.query_api()
            result = await query.query_raw(
                f"from(bucket: \"{visu_config.influx_db.bucket}\") "
                f"|> range(start: {limit}) {element.influx_query}"
            )
            return Response(result, media_type="text/csv")
    except ClientError as ex:
        raise HTTPException(500, f"InfluxDB client error: {ex}") \
            from ex


def main() -> None:
    server_config = uvicorn.Config(
        ".app:app",
        host=visu_config.host,
        port=visu_config.port,
        log_level="debug" if visu_config.uvicorn_debug else "info",
    )
    server = uvicorn.Server(server_config)
    asyncio.run(server.serve())
