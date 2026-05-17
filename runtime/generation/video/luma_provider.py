import os

from .base import VideoProvider


class LumaProvider(VideoProvider):
    name = "luma"
    display_name = "Luma"
    docs_url = "https://lumalabs.ai/"
    env_vars = ("LUMA_API_KEY",)

    def is_configured(self) -> bool:
        return bool(os.environ.get("LUMA_API_KEY"))

