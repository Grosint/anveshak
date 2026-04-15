"""CLIPClassifier — semantic image classification against analyst-defined categories.

Criteria 4.22–4.24:
  4.22: run_clip(media_asset_id, categories) ARQ function (in jobs.py) calls this
  4.23: Categories come from topic.clip_categories (user-defined at topic creation)
  4.24: Results stored in vision_results.clip_labels JSONB

Hardware: openai/clip-vit-base-patch32 on CPU by default.
Upgrade:  CLIP_MODEL_NAME=openai/clip-vit-large-patch14 on GPU (see hardware.md).
"""
from __future__ import annotations

from dataclasses import dataclass

import structlog

from ..settings import settings

log = structlog.get_logger(__name__)


@dataclass
class CLIPResult:
    label: str
    score: float   # 0.0–1.0 cosine similarity


class CLIPClassifier:
    """CLIP zero-shot image classifier.

    Lazy-loads the model on first call. Model name comes entirely from
    settings.clip_model_name — never hardcoded.
    """

    def __init__(self) -> None:
        self._model = None
        self._processor = None

    def _load_model(self) -> None:
        from transformers import CLIPModel, CLIPProcessor

        model_name = settings.clip_model_name
        log.info("vision.clip.loading", model=model_name)
        self._processor = CLIPProcessor.from_pretrained(model_name)  # nosec B615 — sovereign deployment; models pre-cached locally, no runtime HuggingFace download in production
        self._model = CLIPModel.from_pretrained(model_name)  # nosec B615 — sovereign deployment; models pre-cached locally, no runtime HuggingFace download in production
        self._model.eval()
        log.info("vision.clip.loaded", model=model_name)

    def classify(self, image_bytes: bytes, categories: list[str]) -> list[CLIPResult]:
        """Score image against each category using CLIP zero-shot classification.

        Args:
            image_bytes: raw image bytes
            categories:  list of text labels to classify against
                         (from topic.clip_categories — user-defined)

        Returns:
            List of CLIPResult sorted by score descending.
            Empty list if categories is empty.
        """
        if not categories:
            return []

        if self._model is None:
            self._load_model()

        import io
        import torch
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = self._processor(
            text=categories,
            images=image,
            return_tensors="pt",
            padding=True,
        )
        with torch.no_grad():
            outputs = self._model(**inputs)
            # Normalised cosine similarity between image and each text label
            logits = outputs.logits_per_image[0]
            probs = logits.softmax(dim=0).tolist()

        results = [
            CLIPResult(label=cat, score=round(float(p), 4))
            for cat, p in zip(categories, probs)
        ]
        results.sort(key=lambda r: r.score, reverse=True)

        log.debug("vision.clip.classified", top_label=results[0].label if results else None)
        return results

    def to_jsonb(self, results: list[CLIPResult]) -> list[dict]:
        """Serialise for vision_results.clip_labels JSONB column."""
        return [{"label": r.label, "score": r.score} for r in results]
