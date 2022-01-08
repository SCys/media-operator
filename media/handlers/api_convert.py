import os
import subprocess
from datetime import datetime

import ffmpeg
from aiofile import AIOFile, Reader, async_open
from aiohttp.web_response import StreamResponse
from core import BasicHandler
from core.exception import InvalidParams, ServerError
from core.utils import download_to_path, pretty_size
from ffmpy3 import FFmpeg

from .utils import prepare

LIMIT = 10 * 2 << 29  # limit 10G


class APIConvert(BasicHandler):
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

        task, path_input, type_output, mime_type = await prepare(self)

        size = 0

        try:
            self.d(f"downloading {url}")
            await download_to_path(url, path_input, timeout=60, limit=LIMIT)
            self.i(f"downloaded {url}")
        except Exception as e:
            self.x(f"task {task} upload with exception")
            return ServerError()

        await self.process(task, size, type_output, mime_type, path_input)

    async def post(self):
        task, path_input, type_output, mime_type = await prepare(self)

        size = 0

        # read request body
        try:
            async with async_open(path_input, "wb+") as f:
                async for data in self.request.content.iter_chunked(2 << 19):  # 1mb
                    size += len(data)

                    if size > LIMIT:
                        self.e(f"task {task} upload size over limit {pretty_size(LIMIT)}")
                        raise ValueError()

                    await f.write(data)
        except Exception as e:
            self.e(f"task {task} upload with exception:{str(e)}")
            return ServerError()

        await self.process(task, size, type_output, mime_type, path_input)

    async def process(self, task, size, type_output, mime_type, path_input):
        req = self.request

        config = self.config["ffmpeg"]

        options_g = config.get("options_global", "")
        options_i = ""
        options_o = ""

        if type_output == "mp4":
            options_g = config.get("mp4_options_global", "")
            options_i = config.get("mp4_input_options", "")
            options_o = config.get("mp4_output_options", "-f mp4")
        elif type_output == "mkv":
            options_g = config.get("mkv_options_global", "")
            options_i = config.get("mkv_input_options", "")
            options_o = config.get("mkv_output_options", "-f mkv")
        else:
            self.w(f"task {task} unsupported output type:{type_output}")
            raise InvalidParams()

        executable = config.get("ffmpeg", "ffmpeg")
        executable_probe = config.get("ffprobe", "ffprobe")

        path_o = path_input + "." + type_output

        try:
            probe = ffmpeg.probe(path_input, cmd=executable_probe)
        except Exception as e:
            self.x(f"task {task} failed:{str(e)}")
            return

        self.d(f"task {task} is started, input {path_input}({pretty_size(size)}) output {path_o}")

        cost = datetime.now()

        try:
            ff = FFmpeg(
                executable=executable,
                inputs={path_input: options_i},
                outputs={path_o: options_o},
                global_options=options_g,
            )
            await ff.run_async(stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            await ff.wait()
        finally:
            os.unlink(path_input)

        cost = (datetime.now() - cost).total_seconds()
        self.d(f"task {task} is converted, cost {cost}s")

        stat = os.stat(path_o, follow_symlinks=True)
        headers = {
            "X-FFmpeg-Cost-Seconds": str(cost),
            "Content-Type": mime_type,
            "Content-Length": str(stat.st_size),
        }

        await self.history_save(task, type_output, size, stat.st_size, probe, cost)

        try:

            resp = StreamResponse(headers=headers)

            await resp.prepare(req)

            self.d(f"task {task} is sending to client")

            async with AIOFile(path_o, "rb") as f:
                reader = Reader(f, chunk_size=2 << 19)

                async for data in reader:
                    await resp.write(data)
        except Exception as e:
            self.x(f"task {task} stream response failed")
            return ServerError(500, str(e))

        finally:
            os.unlink(path_o)
            self.d(f"task {task} is done")

        return resp

    async def history_save(self, task, type_o, size_i, size_o, probe, cost: float):
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
                    task,
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
            self.e(f"task {task} save history failed:{e}")
