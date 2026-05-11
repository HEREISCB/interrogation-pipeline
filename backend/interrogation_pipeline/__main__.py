"""Entry point: `interrogation-pipeline` (or `python -m interrogation_pipeline`)."""

from __future__ import annotations

import logging

import uvicorn

from interrogation_pipeline.config.settings import settings


def main() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    uvicorn.run(
        "interrogation_pipeline.api.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )


if __name__ == "__main__":
    main()
