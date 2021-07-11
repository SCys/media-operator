from core import Application

import media.handlers


def main():
    app = Application(
        [
            (r"/api/media/convert", media.handlers.APIConvert),
            (r"/api/media/probe", media.handlers.APIProbe),
        ]
    )

    # setup ffmpeg default config
    if not app.config.has_section("ffmpeg"):
        app.config.add_section("ffmpeg")
    app.config["ffmpeg"]["ffmpeg"] = "/opt/ffmpeg/ffmpeg"
    app.config["ffmpeg"]["ffprobe"] = "/opt/ffmpeg/ffprobe"

    app.start()


if __name__ == "__main__":
    main()
