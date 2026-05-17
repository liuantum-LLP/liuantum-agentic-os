import os

from .base import ImageProvider


class ComfyUIProvider(ImageProvider):
    name = "comfyui"
    display_name = "Local Stable Diffusion / ComfyUI"
    docs_url = "https://docs.comfy.org/"
    env_vars = ("COMFYUI_URL",)

    def is_configured(self) -> bool:
        return bool(os.environ.get("COMFYUI_URL"))

