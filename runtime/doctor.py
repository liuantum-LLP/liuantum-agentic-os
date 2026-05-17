from __future__ import annotations

import sys
from typing import Any

from runtime.agents import list_agents
from runtime.connectors.manager import ConnectorManager
from runtime.db import health
from runtime.env_validation import EnvironmentValidator
from runtime.generation.image import ImageGenerationManager
from runtime.generation.video import VideoGenerationManager
from runtime.models import ModelManager


def run_doctor() -> dict[str, Any]:
    db = health()
    env = EnvironmentValidator().check()
    return {
        "status": "ok",
        "python": sys.version.split()[0],
        "database": db,
        "agents_count": len(list_agents()),
        "configured_connectors_count": len(ConnectorManager().list()),
        "models": ModelManager().status(),
        "image_providers": ImageGenerationManager().list_providers(),
        "video_providers": VideoGenerationManager().list_providers(),
        "safe_mode": "draft_only",
        "environment": env,
    }
