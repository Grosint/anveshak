"""Anveshak Analyst Service — entrypoint delegates to scheduler.

The analyst service is split into two containers:
  - analyst-scheduler: lightweight loops (clustering, signals, convergence, orphan sweep)
  - analyst-worker: ARQ-based ML pipeline (NLP, embedding, label gen, credibility)

This module is the default CMD in the Dockerfile. It runs the scheduler.
The worker is started via: python -m arq anveshak.analyst.jobs.WorkerSettings
"""
import asyncio

from .scheduler import main


if __name__ == "__main__":
    asyncio.run(main())
