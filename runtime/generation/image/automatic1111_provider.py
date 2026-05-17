import os

from .base import ImageProvider


class Automatic1111Provider(ImageProvider):
    name = "automatic1111"
    display_name = "Automatic1111 API"
    docs_url = "https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/API"
    env_vars = ("AUTOMATIC1111_URL",)

    def is_configured(self) -> bool:
        return bool(os.environ.get("AUTOMATIC1111_URL"))

