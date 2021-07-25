from asyncio.subprocess import PIPE
import os
import subprocess
from datetime import datetime
from typing import TYPE_CHECKING
from aiofile import AIOFile, Reader, async_open
from aiohttp.web_response import StreamResponse
from core import BasicHandler
from core.exception import ServerError
from core.utils import pretty_size
from ffmpy3 import FFmpeg
import ffmpeg
from xid import Xid

DEFAULT_PATH = "data/media/convert"
LIMIT = 10 * 2 << 29  # limit 10G

DEFAULT_TYPE = "mp4"
SUPPORT_TYPES = {"mp4": "video/mp4"}


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

        type_o = req.query.get("type", DEFAULT_TYPE)
        if type_o not in SUPPORT_TYPES:
            type_o = DEFAULT_TYPE

        mime_type = SUPPORT_TYPES.get(type_o)

        config = self.config["ffmpeg"]

        options_g = config.get("options_global", "")
        options_i = ""
        options_o = ""

        if type_o == "mp4":
            options_g = config.get("mp4_options_global", "")
            options_i = config.get("mp4_input_options", "")
            options_o = config.get("mp4_output_options", "-f mp4")

        executable = config.get("ffmpeg", "ffmpeg")
        executable_probe = config.get("ffprobe", "ffprobe")

        # save upload data
        try:
            if not os.path.isdir(DEFAULT_PATH):
                os.makedirs(DEFAULT_PATH)
        except OSError:
            self.w(f"{DEFAULT_PATH} path is not exists")
            return ServerError()

        id = Xid().string()
        path_i = os.path.join(DEFAULT_PATH, id)

        size = 0

        # 保存源到本地
        try:
            async with async_open(path_i, "wb+") as f:
                async for data in req.content.iter_chunked(2 << 19):  # 1mb
                    size += len(data)

                    if size > LIMIT:
                        self.e(f"task {id} upload size over limit {pretty_size(LIMIT)}")
                        raise ValueError()

                    await f.write(data)
        except Exception as e:
            self.e(f"task {id} upload with exception:{str(e)}")
            return ServerError()

        path_o = path_i + "." + type_o

        try:
            probe = ffmpeg.probe(path_i, cmd=executable_probe)
        except Exception as e:
            self.x(f"task {id} failed:{str(e)}")
            return

        self.d(f"task {id} is started, input {path_i}({pretty_size(size)}) output {path_o}")

        cost = datetime.now()

        try:
            ff = FFmpeg(
                executable=executable,
                inputs={path_i: options_i},
                outputs={path_o: options_o},
                global_options=options_g,
            )
            await ff.run_async(stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            await ff.wait()
        finally:
            os.unlink(path_i)

        cost = (datetime.now() - cost).total_seconds()
        self.d(f"task {id} is converted, cost {cost}s")

        stat = os.stat(path_o, follow_symlinks=True)
        headers = {
            "X-FFmpeg-Cost-Seconds": str(cost),
            "Content-Type": mime_type,
            "Content-Length": str(stat.st_size),
        }

        await self.history_save(id, type_o, size, stat.st_size, probe, cost)

        try:

            resp = StreamResponse(headers=headers)

            await resp.prepare(req)

            self.d(f"task {id} is sending to client")

            async with AIOFile(path_o, "rb") as f:
                reader = Reader(f, chunk_size=2 << 19)

                async for data in reader:
                    await resp.write(data)
        except Exception as e:
            self.x(f"task {id} stream response failed")
            return ServerError(500, str(e))

        finally:
            os.unlink(path_o)
            self.d(f"task {id} is done")

        return resp

    async def history_save(self, id, type_o, size_i, size_o, probe, cost: float):
        if not self.db:
            return

        req = self.request

        input_video_codec = None
        input_audio_codec = None
        input_width = None
        input_height = None

        video_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "video"), None)
        if video_stream:
            input_video_codec = video_stream["codec_name"]
            input_width = video_stream["width"]
            input_height = video_stream["height"]

        audio_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "audio"), None)
        if audio_stream:
            input_audio_codec = audio_stream["codec_name"]

        try:
            async with self.db.acquire(timeout=5) as conn:
                await conn.execute(
                    """insert into media_history(
                        id, info,
                        input_size,input_video_codec,input_audio_codec,input_width,input_height,
                        output_size,output_video_codec,
                        cost
                    ) values(
                        $1,$2,
                        $3,$4,$5,$6,$7,
                        $8,$9,
                        $10
                    )
                    """,
                    id,
                    {"source": req.remote},
                    size_i,
                    input_video_codec,
                    input_audio_codec,
                    input_width,
                    input_height,
                    size_o,
                    type_o,
                    int(cost * 1000),
                )
        except Exception as e:
            self.e(f"task {id} save history failed:{e}")
