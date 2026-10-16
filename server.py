#!/usr/bin/env python3
"""Atalho para iniciar o musicweb: python server.py [PASTA_DE_MUSICAS] [--port 8080] [--config arquivo]

O código fica no pacote musicweb/ e a configuração no config.toml (veja o README.md).
"""
from musicweb.app import main

if __name__ == "__main__":
    main()
