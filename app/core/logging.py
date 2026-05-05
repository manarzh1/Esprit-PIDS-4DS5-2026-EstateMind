"""app/core/logging.py — Logging structure avec structlog."""
import logging
import structlog

def get_logger(name: str):
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return structlog.get_logger(name)
