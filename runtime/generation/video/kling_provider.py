import os

from .base import VideoProvider


class KlingProvider(VideoProvider):
    name = "kling"
    display_name = "Kling"
    docs_url = "https://app.klingai.com/"
    env_vars = ("KLING_API_KEY",)

    def is_configured(self) -> bool:
        return bool(os.environ.get("KLING_API_KEY"))

