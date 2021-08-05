from core.web import BasicHandler
import os

from aiohttp.web import Request
from core.exception import ServerError
from xid import Xid

DEFAULT_TYPE = "mp4"
SUPPORT_TYPES = {"mp4": "video/mp4"}
DEFAULT_PATH = "data/media/convert"


async def prepare(handler: BasicHandler):
    req = handler.request

    type_output = req.query.get("type", DEFAULT_TYPE)
    if type_output not in SUPPORT_TYPES:
        type_output = DEFAULT_TYPE

    mime_type = SUPPORT_TYPES.get(type_output)

    # save upload data
    try:
        if not os.path.isdir(DEFAULT_PATH):
            os.makedirs(DEFAULT_PATH)
    except OSError:
        handler.w("Can't create directory")
        return ServerError()

    id = Xid().string()
    path_input = os.path.join(DEFAULT_PATH, id)

    return id, path_input, type_output, mime_type
