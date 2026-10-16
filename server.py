#!/usr/bin/env python3
"""Shortcut to start musicweb: python server.py [MUSIC_DIR] [--port 8080] [--config FILE]

The code lives in the musicweb/ package and the settings in config.toml (see README.md).
"""
from musicweb.app import main

if __name__ == "__main__":
    main()
