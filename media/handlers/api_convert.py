import os

from aiofile import AIOFile, Reader, async_open
from aiohttp.web_response import StreamResponse
from core import BasicHandler
from core.utils import pretty_size
from core.web import ServerError
from ffmpy3 import FFmpeg
from xid import Xid

DEFAULT_PATH = "data/media/convert"
LIMIT = 10 * 2 << 29  # limit 10G

DEFAULT_TYPE = "mp4"
SUPPORT_TYPES = {"mp4": "h264", "webm": "vp09"}


class APIConvert(BasicHandler):
    """convert uploaded media file to mp4 container

    url params:
    - async: service will convert media in background
    - url: if start with http(s) will do a request when async task is done
    """

    async def post(self):
        await self.process()

    async def put(self):
        await self.process()

    async def process(self):
        req = self.request

        # do_async = "async" in req.query
        # url = req.query.get("url")

        type = req.query.get("type", DEFAULT_TYPE)
        if type not in SUPPORT_TYPES:
            type = DEFAULT_TYPE
        codec = SUPPORT_TYPES.get(type, SUPPORT_TYPES[DEFAULT_TYPE])

        # mp4 spec encodec
        if type == "mp4" and "ffmpeg" in self.config:
            codec = self.config["ffmpeg"].get("mp4_encodec", "h264")

        # save upload data
        try:
            if not os.path.isdir(DEFAULT_PATH):
                os.makedirs(DEFAULT_PATH)
        except OSError:
            self.w(f"{DEFAULT_PATH} path is not exists")
            return ServerError()

        id = Xid().string()
        path_in = os.path.join(DEFAULT_PATH, id)

        size = 0

        try:
            async with async_open(path_in, "wb+") as fobj:
                async for data in req.content.iter_chunked(2 << 19):  # 1mb
                    size += len(data)

                    if size > LIMIT:
                        self.e(f"task {id} upload size over limit {pretty_size(LIMIT)}")
                        raise ValueError()

                    await fobj.write(data)
        except:
            self.x(f"task {id} upload with exception")
            return ServerError()

        self.d(f"task {id} save data size {pretty_size(size)}")

        # if do_async:
        #     return {"id": id, "size": size}

        path_out = path_in + ".mp4"

        self.d(f"task {id} is started, input:{path_in} output {path_out}")

        try:
            ff = FFmpeg(inputs={path_in: None}, outputs={path_out: f"-c:v {codec} -f {type}"}, global_options=["-v warning"])
            await ff.run_async()
            await ff.wait()

            self.d(f"task {id} is converted")
        finally:
            os.unlink(path_in)

        try:
            stat = os.stat(path_out, follow_symlinks=True)

            resp = StreamResponse()
            resp.content_length = stat.st_size
            resp.content_type = "video/mp4"

            await resp.prepare(req)

            self.d(f"task {id} is sending to client")

            async with AIOFile(path_out, "rb") as fobj:
                reader = Reader(fobj, chunk_size=2 << 19)

                async for data in reader:
                    await resp.write(data)

            return resp
        finally:
            os.unlink(path_out)
            self.d(f"task {id} is done")
