import os

from .base import VideoProvider


class OpenAISoraProvider(VideoProvider):
    name = "openai_sora"
    display_name = "OpenAI Sora API"
    docs_url = "https://platform.openai.com/docs"
    env_vars = ("OPENAI_API_KEY",)

    def is_configured(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

