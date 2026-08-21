"""Vision detector implementations.

Factory function `get_deepfake_detector` instantiates the correct detector
based on settings — no conditional imports scattered across the codebase.
"""

from .base import DeepfakeDetector
from .clip_detector import CLIPClassifier
from .yolo_detector import YOLODetector


def get_deepfake_detector(model_type: str, device: str) -> DeepfakeDetector:
    """Return the correct DeepfakeDetector for the configured model type.

    Criteria 4.13, 4.17–4.19: instantiated by settings, never hardcoded.
    """
    if model_type == "facetorch":
        from .facetorch import FacetorchDetector

        return FacetorchDetector(device=device)
    if model_type == "efficientnet":
        from .efficientnet import EfficientNetDetector

        return EfficientNetDetector(device=device)
    if model_type == "dire":
        from .dire import DIREDetector

        return DIREDetector(device=device)
    raise ValueError(
        f"Unknown deepfake model type: {model_type!r}. Valid values: facetorch, efficientnet, dire"
    )


__all__ = ["DeepfakeDetector", "YOLODetector", "CLIPClassifier", "get_deepfake_detector"]
