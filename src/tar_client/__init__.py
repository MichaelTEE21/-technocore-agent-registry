"""Lightweight tar.a2a client. Not UI-dependent. No private keys by default."""

from tar_client.client import TarClient, TarClientError, connect

__all__ = ["TarClient", "TarClientError", "connect"]
