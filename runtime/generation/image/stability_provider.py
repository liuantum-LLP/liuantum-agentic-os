import os

from .base import ImageProvider


class StabilityProvider(ImageProvider):
    name = "stability"
    display_name = "Stability AI"
    docs_url = "https://platform.stability.ai/docs/api-reference"
    env_vars = ("STABILITY_API_KEY",)

    def is_configured(self) -> bool:
        return bool(os.environ.get("STABILITY_API_KEY"))

