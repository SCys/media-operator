# media operator

![Docker Image](https://github.com/SCys/media-operator/actions/workflows/docker.yml/badge.svg)
[![Docker](https://img.shields.io/docker/pulls/scys/media-operator.svg)](https://hub.docker.com/r/scys/media-operator)
![License](https://img.shields.io/github/license/scys/media-operator.svg)

Docker image platforms include amd64 and arm64

## Quick start

run in shell and listen on 8080 port

```bash
docker run -it --rm -v $PWD/main.ini:/app/main.ini -p 8080:8080 scys/media-operator:latest
```

## Docker

docker image is [scys/media-operator](https://hub.docker.com/r/scys/media-operator)

## Depeneds and Thanks

python libs

- [aiohttp](https://docs.aiohttp.org)
- [orjson](https://github.com/ijl/orjson)
- [loguru](https://github.com/Delgan/loguru)
- [asyncpg](https://github.com/MagicStack/asyncpg)
- [uvloop](https://github.com/MagicStack/uvloop)
- [aiofile](https://github.com/mosquito/aiofile)
- [ffmpy3](https://ffmpy3.readthedocs.io)
- [ffmpeg-python](https://github.com/kkroening/ffmpeg-python)

and [FFmpeg](http://ffmpeg.org/)

and [johnvansickle.com ffmpeg static build](https://johnvansickle.com/ffmpeg/)
