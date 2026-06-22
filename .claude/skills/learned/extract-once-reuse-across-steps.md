# Extract Once, Reuse Across Pipeline Steps

## Problem

Video vision pipeline called `extract_keyframes()` inside `_analyse_video()` for
deepfake only. To add YOLO, CLIP, pHash for video, the naive approach would call
`extract_keyframes()` three more times — 4x ffmpeg subprocess launches on the
same file.

## Rule

When a pipeline has a shared expensive input (frame extraction, embedding generation,
API fetch), extract it ONCE at the top of the pipeline and pass the result to each step.

Pattern:
```python
# WRONG — each step extracts independently
if is_video:
    deepfake_score = await _analyse_video(path)  # extracts frames internally
    yolo_results = await _yolo_video(path)        # extracts frames again
    clip_results = await _clip_video(path)        # extracts frames again

# RIGHT — extract once, pass to all
if is_video:
    frames = await extract_keyframes(path)
    if len(frames) > settings.max_frames:
        frames = _even_sample(frames, settings.max_frames)
    deepfake_score = await _deepfake_video_frames(frames)
    yolo_results = await _aggregate_yolo_frames(frames)
    clip_results = await _aggregate_clip_frames(frames)
```

## Aggregation strategies per step

Each step needs a different aggregation across frames:
- **Deepfake**: worst-case (max score) — one fake frame = suspicious video
- **YOLO**: union with dedup by label (keep highest confidence per class)
- **CLIP**: best score per category across all frames
- **pHash**: first frame only (representative thumbnail)

## Frame cap

Long videos produce many frames. Cap with `video_max_analysis_frames` setting +
even sampling (`frames[int(i * step)]`) to bound resource usage without losing
temporal coverage.

## See also

- `arq-worker-ml-singleton.md` — load models once per worker, similar principle
