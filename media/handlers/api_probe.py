from asyncio import subprocess
import os

from aiofile import async_open
from core import BasicHandler
from core.utils import pretty_size
from core.web import ObjectNotFound, ServerError
from xid import Xid
import ffmpeg

DEFAULT_PATH = "data/media/probe"
LIMIT = 10 * 2 << 29  # limit 10G


class APIProbe(BasicHandler):
    """convert uploaded media file to mp4 container

    url params:
    - async: service will convert media in background
    - url: if start with http(s) will do a request when async task is done
    """

    async def post(self):
        return await self.process()

    async def put(self):
        return await self.process()

    async def process(self):
        req = self.request

        # save upload data
        try:
            if not os.path.isdir(DEFAULT_PATH):
                os.makedirs(DEFAULT_PATH)
        except OSError:
            self.w(f"{DEFAULT_PATH} path is not exists")
            return ServerError()

        if "ffmpeg" in self.config:
            executable = self.config["ffmpeg"].get("ffprobe", "ffprobe")
        else:
            executable = "ffprobe"

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

        try:
            probe = ffmpeg.probe(path_in, cmd=executable)
        except ffmpeg.Error as e:
            self.e(f"task {id} failed:{str(e)}")
            return ServerError(500, str(e))
        finally:
            os.unlink(path_in)
            self.d(f"task {id} is done")

        video_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "video"), None)
        if video_stream is None:
            self.w("task {id} do not have any video stream")
            return ObjectNotFound()

        return {"data": video_stream}
