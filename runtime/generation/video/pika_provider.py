import os

from .base import VideoProvider


class PikaProvider(VideoProvider):
    name = "pika"
    display_name = "Pika"
    docs_url = "https://pika.art/"
    env_vars = ("PIKA_API_KEY",)

    def is_configured(self) -> bool:
        return bool(os.environ.get("PIKA_API_KEY"))

