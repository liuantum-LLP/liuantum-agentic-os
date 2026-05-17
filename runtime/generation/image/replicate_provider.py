import os

from .base import ImageProvider


class ReplicateProvider(ImageProvider):
    name = "replicate"
    display_name = "Replicate Image Models"
    docs_url = "https://replicate.com/docs"
    env_vars = ("REPLICATE_API_TOKEN",)

    def is_configured(self) -> bool:
        return bool(os.environ.get("REPLICATE_API_TOKEN"))

