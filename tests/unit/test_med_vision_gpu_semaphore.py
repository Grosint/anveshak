"""Unit tests for vision GPU inference semaphore — MED-18.

Concurrent deepfake inference on GPU causes CUDA kernel conflicts.
A semaphore must serialize GPU-bound inference calls.
"""
from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.unit


class TestVisionGPUSemaphore:

    def test_inference_semaphore_exists(self):
        """Vision jobs module must have an _inference_semaphore."""
        from anveshak.vision import jobs as vision_jobs

        assert hasattr(vision_jobs, "_inference_semaphore"), (
            "Vision jobs must have _inference_semaphore to serialize GPU inference"
        )
        sem = vision_jobs._inference_semaphore
        assert isinstance(sem, asyncio.Semaphore), (
            "_inference_semaphore must be an asyncio.Semaphore"
        )

    def test_semaphore_value_is_one(self):
        """Semaphore must allow only 1 concurrent inference (GPU not thread-safe)."""
        from anveshak.vision import jobs as vision_jobs

        sem = vision_jobs._inference_semaphore
        # Semaphore(1) has _value=1 initially
        assert sem._value == 1, (
            "Inference semaphore must be Semaphore(1) for GPU safety"
        )
