import os

from .base import VideoProvider


class RunwayProvider(VideoProvider):
    name = "runway"
    display_name = "Runway"
    docs_url = "https://docs.dev.runwayml.com/"
    env_vars = ("RUNWAY_API_KEY",)

    def is_configured(self) -> bool:
        return bool(os.environ.get("RUNWAY_API_KEY"))

