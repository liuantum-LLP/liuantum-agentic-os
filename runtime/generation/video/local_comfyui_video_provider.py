import os

from .base import VideoProvider


class LocalComfyUIVideoProvider(VideoProvider):
    name = "local_comfyui_video"
    display_name = "Local ComfyUI Video Workflow"
    docs_url = "https://docs.comfy.org/"
    env_vars = ("COMFYUI_URL",)

    def is_configured(self) -> bool:
        return bool(os.environ.get("COMFYUI_URL"))

