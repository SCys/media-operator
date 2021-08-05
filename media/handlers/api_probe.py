import os

import ffmpeg
from aiofile import async_open
from core import BasicHandler
from core.exception import InvalidParams, ObjectNotFound, ServerError
from core.utils import download_to_path, pretty_size
from xid import Xid

from .utils import prepare

DEFAULT_PATH = "data/media/probe"
LIMIT = 10 * 2 << 29  # limit 10G


class APIProbe(BasicHandler):
    """convert uploaded media file to mp4 container

    url params:
    - async: service will convert media in background
    - url: if start with http(s) will do a request when async task is done
    """

    async def get(self):
        # download from url
        url = self.request.query.get("url")
        if not url:
            return InvalidParams()

        id = Xid().string()
        path_input = os.path.join(DEFAULT_PATH, id)

        try:
            self.d(f"downloading {url}")
            await download_to_path(url, path_input, timeout=60, limit=LIMIT)
            self.i(f"downloaded {url}")
        except Exception as e:
            self.e(f"task {id} upload with exception:{str(e)}")
            return ServerError()

        return await self.process(id, path_input)

    async def put(self):
        size = 0
        id = Xid().string()
        path_input = os.path.join(DEFAULT_PATH, id)

        # read request body
        try:
            async with async_open(path_input, "wb+") as f:
                async for data in self.request.content.iter_chunked(2 << 19):  # 1mb
                    size += len(data)

                    if size > LIMIT:
                        self.e(f"task {id} upload size over limit {pretty_size(LIMIT)}")
                        raise ValueError()

                    await f.write(data)
        except Exception as e:
            self.e(f"task {id} upload with exception:{str(e)}")
            return ServerError()

        return await self.process(id, size, path_input)

    async def process(self, id, size, path_input):
        if "ffmpeg" in self.config:
            executable = self.config["ffmpeg"].get("ffprobe", "ffprobe")
        else:
            executable = "ffprobe"

        self.d(f"task {id} save data size {pretty_size(size)}")

        try:
            probe = ffmpeg.probe(path_input, cmd=executable)
        except ffmpeg.Error as e:
            self.e(f"task {id} failed:{str(e)}")
            return ServerError(500, str(e))
        finally:
            os.unlink(path_input)
            self.d(f"task {id} is done")

        video_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "video"), None)
        audio_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "audio"), None)

        return {"data": {"audio": audio_stream, "video": video_stream}, "id": id}
