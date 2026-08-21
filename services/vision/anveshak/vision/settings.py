from pathlib import Path

from pydantic_settings import BaseSettings


class VisionSettings(BaseSettings):
    postgres_url: str = "postgresql://anveshak:anveshak@localhost:5432/anveshak"
    redis_url: str = "redis://localhost:6379"

    # Hardware-controlled settings — see hardware.md
    vision_device: str = "cpu"  # cpu → cuda (see hardware.md)
    yolo_model_size: str = "nano"  # nano → xlarge (see hardware.md)
    vision_deepfake_image_model: str = "facetorch"  # facetorch (upgradeable)
    vision_deepfake_video_model: str = "efficientnet"  # efficientnet → dire (see hardware.md)
    vision_batch_size: int = 1  # increase on GPU (see hardware.md)

    # Model directory — populated by Dockerfile pre-download step
    # Never hardcode model names in service logic — always read from here
    model_dir: Path = Path("/app/models")

    # YOLO model filenames — each size maps to a model file under model_dir/yolo/
    # Upgrade path: change yolo_model_size env var only (see hardware.md)
    yolo_model_nano: str = "yolov8n.pt"
    yolo_model_small: str = "yolov8s.pt"
    yolo_model_medium: str = "yolov8m.pt"
    yolo_model_large: str = "yolov8l.pt"
    yolo_model_xlarge: str = "yolov8x.pt"
    yolo_confidence_threshold: float = 0.25

    # CLIP — hardware.md: openai/clip-vit-base-patch32 → clip-vit-large-patch14 on GPU
    clip_model_name: str = "openai/clip-vit-base-patch32"

    # HuggingFace model sources for deepfake detectors
    # Swappable via env var — no code change to upgrade models
    facetorch_hf_model: str = "prithivMLmods/Deep-Fake-Detector-v2-Model"
    efficientnet_hf_model: str = "umm-maybe/AI-image-detector"

    # Deepfake model paths (relative to model_dir)
    facetorch_model_path: str = "facetorch/face_deepfake.onnx"
    efficientnet_model_path: str = "efficientnet/deepfake_b0.onnx"
    deepfake_face_confidence_threshold: float = 0.5
    deepfake_high_risk_threshold: float = 0.8  # triggers credibility downgrade (criteria 4.33)

    # Video keyframe extraction
    video_keyframe_interval_s: int = 5
    vision_max_video_size_mb: int = 500
    video_max_analysis_frames: int = 30  # cap frames for YOLO/CLIP on long videos

    # pHash reverse lookup
    phash_duplicate_threshold: int = 8

    # Media storage root (must match scraper/social MEDIA_STORAGE_ROOT)
    media_storage_root: Path = Path("/app/media")

    # Media retention: delete files older than N days where vision analysis is complete.
    # 0 = disabled (keep forever). Files are deleted, DB metadata is preserved.
    media_retention_days: int = 30

    # EXIF backend — pillow (stdlib) or exiftool (binary must be on PATH)
    exif_backend: str = "pillow"  # pillow → exiftool via env

    port: int = 8003
    log_level: str = "INFO"
    model_config = {"env_prefix": "", "case_sensitive": False}

    def yolo_model_file(self) -> str:
        """Return the YOLO model filename for the configured size.
        Zero code change required when upgrading from nano → xlarge.
        """
        _map = {
            "nano": self.yolo_model_nano,
            "small": self.yolo_model_small,
            "medium": self.yolo_model_medium,
            "large": self.yolo_model_large,
            "xlarge": self.yolo_model_xlarge,
        }
        return _map.get(self.yolo_model_size, self.yolo_model_nano)


settings = VisionSettings()
