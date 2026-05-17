#!/usr/bin/env python3
"""
Sidecar entry point for PyInstaller/Nuitka builds.
This script is the target for building a standalone backend executable.
"""
import sys
import os

# Ensure the project root is on the path
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_this_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from cli.liuant import main

if __name__ == "__main__":
    main()
