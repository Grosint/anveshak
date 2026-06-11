# HSE Vision Detection — Architecture Plan (v2)

**Last updated:** 2026-06-03
**Status:** Research-validated, team-reviewed

## Overview

31 HSE (Health, Safety & Environment) use cases for oil rig / drilling site safety monitoring.
Architecture: **5 models + 3 logic layers**, validated against production HSE systems
(Voxel AI, Intenseye, Detect Technologies, viAct) and 80+ research papers (2024-2026).

---

## Architecture Audit — Team's 3-Model Split

The team proposed splitting the original single detection model into 3 domain-specific models:
PPE, Fire/Smoke, and Machinery. This section documents the research-backed audit of that decision.

### VERDICT: APPROVED with modifications

The team's instinct is validated by production evidence:

1. **Every production HSE vendor uses multiple specialized models**, not one unified model.
   Voxel AI, Intenseye, Detect Technologies all deploy per-domain models.

2. **Domain gap is real.** PPE datasets are person-centric close-ups. Fire/smoke datasets are
   wide-angle amorphous blobs. Machinery datasets are large-scale industrial equipment.
   Mixing these causes class imbalance, anchor size conflicts, and augmentation conflicts.

3. **3x YOLOv8m (77.7M params total) is lighter than 1x YOLOv8x (68.2M params)** in params,
   but can run in parallel on GPU for identical latency. On CPU, sequential 3x medium is
   ~30ms vs ~20ms for 1x large — acceptable at drilling site frame rates (5-15 FPS).

### Modifications from research

| Team Proposal | Research Finding | Recommendation |
|---|---|---|
| PPE as YOLOv8m | YOLOv8m is the sweet spot for PPE (Cogent Engineering 2024). YOLOv8l only needed for hard items (gloves, harness). | **APPROVED.** Use YOLOv8m. Consider two-stage (detect person, then classify PPE per crop) for gloves/harness. |
| Fire/Smoke as YOLOv8s | YOLOv8s is insufficient alone. Small fires at distance have low recall. Temporal verification is mandatory. | **MODIFY.** Use YOLOv8m (not s) + mandatory temporal filtering (3-5 consecutive frames). Consider EFA-YOLO (1.4M params, 22ms on CPU) as alternative. |
| Machinery as YOLOv8m | No counter-evidence found. | **APPROVED.** |
| Fog/haze in fire model | Research says NO. Fog and smoke are visually confounded. Joint training creates misclassification. Dehazing preprocessing actually harms detection on clear images. | **REJECT.** Keep fog/visibility as a separate image-quality metric (Laplacian variance + histogram spread). No ML needed. |

---

## Use Case Inventory

| # | HSE Use Case | Mandatory | Category | Model |
|---|---|---|---|---|
| 1 | PPE – Helmet Detection | M | A: Object Detection | PPE |
| 2 | PPE – Gloves Detection | M | A: Object Detection | PPE (hard) |
| 3 | PPE – Goggles Detection | M | A: Object Detection | PPE (hard) |
| 4 | PPE – Safety Harness Detection | M | A: Object Detection | PPE (hard) |
| 5 | Fire Detection | M | A: Object Detection | Hazard |
| 6 | Welding + Multi-person Detection | M | D: Pose/Action | Pose + PPE |
| 7 | Poor Visibility Detection | M | E: Scene Understanding | No ML (image metrics) |
| 8 | Smoke Detection | M | A: Object Detection | Hazard |
| 9 | Crane Safety Zone Violation | M | B: Zone Violation | PPE + Zone Engine |
| 10 | Housekeeping Violation (untidy site, 6am/6pm) | M | E: Scene Understanding | VLM (not CLIP) |
| 11 | Unauthorized Entry – Driller Cabin | M | B: Zone Violation | PPE + Zone Engine |
| 12 | High-Speed Vehicle Detection | M | C: Temporal/Duration | Machinery + Tracker |
| 13 | Improper Coverall Clothing Detection | M | A: Object Detection | PPE (hard) |
| 14 | 3-Point Contact Violation – Handrails | M | D: Pose/Action | Pose + Machinery |
| 15 | Line of Fire – Moving Vehicle | M | C: Temporal/Duration | Machinery + Tracker |
| 16 | Catwalk Red Zone Violation | M | B: Zone Violation | PPE + Zone Engine |
| 17 | Green Helmet Alone in Restricted Zone | M | B: Zone Violation | PPE + Zone Engine |
| 18 | Worker Gathering (>=4 persons) | M | C: Temporal/Duration | PPE + Tracker |
| 19 | Drilling Red Zone Intrusion | M | B: Zone Violation | PPE + Zone Engine |
| 20 | Catwalk Waiting > 1 Minute | M | C: Temporal/Duration | PPE + Tracker + Zone |
| 21 | Vertical Door Red Zone – Presence >=3s | M | B+C: Zone + Timer | PPE + Tracker + Zone |
| 22 | Unsafe Stair Descent | M | D: Pose/Action | Pose |
| 23 | Line of Fire – Elevator | M | C: Temporal/Duration | Machinery + Tracker |
| 24 | Unsafe Elevator Descent | M | C: Temporal/Duration | Machinery + Tracker |
| 25 | Line of Fire – Iron Roughneck | M | D: Pose/Action | Pose + Machinery |
| 26 | Under Suspended Load – Power Tong >=4s | M | C: Temporal/Duration | Machinery + Tracker |
| 27 | Under Suspended Load – Manual Tong >=4s | M | C: Temporal/Duration | Machinery + Tracker |
| 28 | Unsafe Work at Height – BOP | M | B: Zone Violation | PPE + Zone Engine |
| 29 | Hands/Fingers Near Equipment Pinch Points | M | D: Pose/Action | Pose + Machinery |
| 30 | Covered or Dirty Camera >=10 seconds | M | A+C: Detection + Timer | Hazard + Timer |
| 31 | Suspended Load – Pipes in Vertical Door | M | C: Temporal/Duration | Machinery + Tracker |

---

## Detection Models (5 total)

### Model 1: PPE Detector — YOLOv8m (custom trained)

**Classes:** helmet, white_helmet, green_helmet, yellow_helmet, red_helmet,
gloves, goggles, safety_vest, safety_harness, coverall, person, no_helmet, no_vest

**Architecture decision — two-stage pipeline recommended:**

Production systems (Intenseye, Voxel AI) increasingly use two-stage:
1. Stage 1: Detect persons (YOLOv8m, high recall)
2. Stage 2: Classify PPE per person crop (smaller classifier on ROI)

This is more robust than single-stage for compliance association ("which person is non-compliant?")
and dramatically improves detection of small items (gloves, goggles).

**Known hard cases (from production deployments):**

| Item | Expected mAP@50 | Challenge | Mitigation |
|---|---|---|---|
| Helmet | 79-100% | Easiest PPE item | Standard detection |
| Helmet color | ~85% at <20m | Degrades at distance | High-res cameras in color-critical zones |
| Safety vest | 73-95% | Large, high-contrast | Standard detection |
| Gloves | ~60-70% | Tiny objects, occlusion, skin-color confusion | Pose-guided ROI (crop hand region), checkpoint cameras |
| Goggles | ~55-65% | Small, easily occluded by helmet | Close-range checkpoint cameras |
| Harness | 70-81% | Thin straps, confused with clothing folds | YOLOv5+OpenPose approach (89% acc), close-range only |
| Coverall (improper) | Unsolved | No objective definition of "improper" | Frame as coverage percentage via segmentation |

**Color-as-class approach for helmets:** One class per color (CHV dataset standard).
Do NOT use a separate classifier head — single-stage with color classes is proven at 86-92% mAP.

**Datasets:** SH17 (8,099 images, 17 classes, manufacturing, global diversity),
CHV (1,330 images, 6 classes, color helmets), Roboflow PPE collections.

### Model 2: Hazard Detector — YOLOv8m (custom trained)

**Classes:** fire, smoke

**CRITICAL: YOLOv8s is NOT recommended.** Research findings:
- YOLOv8m is the ONLY medium variant showing clear improvement over small (2025 YOLO study)
- YOLOv8s has low recall on small fires at distance — insufficient for early detection
- Baseline YOLOv8 achieves ~78-79% mAP@50 on D-Fire without modifications

**Mandatory: Temporal verification layer.**
Single-frame fire/smoke detection is a false positive factory. Production systems require:
- Detection persistence across 3-5 consecutive frames before alerting
- Zone-based sensitivity (higher threshold near welding stations — welding sparks are #1 false positive)
- Background subtraction to reject stationary flame-like objects (orange machinery, sunset reflections)

**False positive sources in oil & gas:**
- Welding arcs and sparks (short-duration, high-intensity)
- Steam and exhaust (sustained, diffuse — similar to smoke)
- Sunset/sunrise sky colors
- Hot process surfaces
- Dust particles

**Expected false positive rate:** 2-5% with temporal filtering + zone sensitivity. 10-30% without.

**Alternative models worth evaluating:**
- EFA-YOLO: 1.4M params, 22ms on CPU, 94.6% fewer params than YOLOv8. Best for edge.
- YOLO-FireAD: 1.45M params, outperforms YOLOv8n/v9t/v10n/v11n at mAP75.
- Fire-YOLO26: Dual-stream RGB+thermal. Best if thermal cameras are available.

**Datasets:** D-Fire (21K images, CC0 license), MS-FSDB (12,586 images, best generalization benchmark).
Add industrial-specific negatives (welding, steam, exhaust) from deployment environment.

**Fog/haze is NOT in this model.** Fog and smoke are visually confounded — joint training increases
misclassification. Poor visibility (use case 7) uses image quality metrics instead:
- Laplacian variance for blur detection
- Histogram spread for fog/haze
- No ML model required

### Model 3: Machinery/Equipment Detector — YOLOv8m (custom trained)

**Classes:** crane, crane_load, pipe, tong, elevator, vehicle, forklift, suspended_load

**Purpose:** Detects industrial equipment for zone violation, line-of-fire, and
suspended-load use cases. Person detection comes from Model 1; this model provides
the "what is the person near?" context.

**Suspended load detection specifics (from research):**
- Height difference of ~2 meters from ground classifies object as "suspended" vs "resting"
- Fall zone modeled as a cone/cylinder beneath the load (includes swing radius)
- Stereo depth or known crane geometry needed for elevation estimation
- Published performance: 94% precision, 96.5% recall at 8 FPS

### Model 4: Pose Estimator — YOLOv8m-pose (pretrained)

**No training needed.** Pretrained YOLOv8-pose provides 17 body keypoints per person.

**Why YOLOv8-pose over alternatives:**

| Framework | Industrial Use Case | Verdict |
|---|---|---|
| YOLOv8-Pose | Multi-person, single-pass, handles occlusion/crowds | Best for multi-worker sites |
| MediaPipe | Ultra-low latency, single-person only | Only for single-operator edge (body cam) |
| OpenPose | Bottom-up, handles groups | Legacy, slowest — do not use |

**Use case mapping:**
- 3-point contact (14): >= 3 of {hands, feet} keypoints near ladder/handrail bbox
- Hands near pinch points (29): hand keypoints inside equipment danger zone polygon
- Unsafe stair descent (22): body orientation keypoints relative to stair region
- Welding multi-person (6): person count + pose proximity to welding zone
- Line of fire — iron roughneck (25): person keypoints inside equipment movement corridor

**No off-the-shelf model exists for 3-point contact.** The approach is:
detect ladder (Model 3) + run pose (Model 4) + geometric relationship analysis.

### Model 5: Scene Understanding — Small VLM (for housekeeping only)

**CLIP is NOT recommended for housekeeping violations.** Research findings:
- CLIP aligns global features — cannot reason about "this object is in the wrong location"
- Same stack of rebar may be acceptable to one inspector and unacceptable to another
- Zero-shot CLIP for industrial anomaly detection suffers from ignoring local features
- VLMs (Gemini, Qwen-2.5-VL) show improvement but "high recall, low precision"
- "Fully automated inspection is unrealistic today" (Cambridge Core 2025)

**Recommended approach:**
1. YOLO detector (Model 3) identifies objects in the scene
2. Small VLM (Qwen-2.5-VL 7B, runs on Ollama) receives structured prompt with detections
3. VLM provides contextual judgment ("rebar stored improperly near walkway")
4. **Human review is mandatory** — VLM flags, analyst decides

This applies ONLY to use case 10 (housekeeping). All other use cases use deterministic logic.

---

## Logic Layers (3 total)

### Layer 1: Zone Engine (polygon-based spatial reasoning)

**How production systems do this:**
- Operator draws polygon vertices on a camera snapshot (browser-based UI)
- Stored as array of (x, y) coordinates per camera
- Point-in-polygon test: ray casting algorithm (Shapely library, faster than OpenCV bitwise)
- Person foot-point (bottom-center of bbox) tested against zone polygon

**Zone types:**

| Zone | Type | Use Cases |
|---|---|---|
| Crane safety zone | Static (around crane base + swing radius) | 9 |
| Driller cabin | Static exclusion zone | 11 |
| Catwalk red zone | Static exclusion zone | 16, 20 |
| Restricted zone | Static + role-based (green helmet = trainee) | 17 |
| Drilling red zone | Static exclusion zone | 19 |
| Vertical door zone | Static + duration timer | 21 |
| BOP work-at-height | Static + pose check | 28 |
| Equipment movement corridor | Semi-static (predefined path, not real-time trajectory) | 15, 23, 25 |
| Suspended load fall zone | Dynamic (cone/cylinder below detected load) | 26, 27, 31 |

**Line-of-fire implementation (from SPE paper):**
Most production systems use predefined movement corridors (static polygons along known equipment
paths), NOT real-time trajectory prediction. True trajectory prediction remains a research topic.

**Dynamic zones (crane load):**
The fall zone polygon updates based on detected load position. Model 3 detects the load,
zone engine projects a cone beneath it. This is the one dynamic zone in the system.

**Camera calibration:**
- Speed estimation (use case 12) REQUIRES camera calibration via homography
- Accuracy with calibration: 95.1% minimum, 97.6% average (Nature 2025)
- Without calibration: pixel displacement alone is unreliable (perspective distortion)
- Calibration method: 8+ matching landmark points between camera view and floor plan

**Production tooling:** Roboflow `supervision` library provides `PolygonZone` for prototyping.
NVIDIA DeepStream for production deployment.

### Layer 2: Object Tracker — OC-SORT (recommended over ByteTrack)

**Research-backed tracker selection:**

| Metric (MOT17) | ByteTrack | BoT-SORT | OC-SORT | Deep OC-SORT |
|---|---|---|---|---|
| MOTA | 80.3 | 80.5 | 79.4 | ~80.6 |
| IDF1 | 77.3 | 80.2 | 77.5 | ~80.4 |
| Speed | ~30 FPS (GPU) | ~20 FPS | **Hundreds FPS (CPU)** | ~20 FPS |
| Occlusion handling | Low-conf rescue | ReID features | **Observation-centric re-update** | ReID + re-update |

**Why OC-SORT over ByteTrack:**
- Handles occlusion via virtual trajectory correction (person walks behind equipment, reappears)
- Runs at hundreds of FPS on CPU — leaves GPU budget entirely for detection models
- Nearly as accurate as BoT-SORT for identity maintenance
- No appearance embedding model needed (unlike BoT-SORT/Deep OC-SORT)

**Duration-based violation reliability:**
- At 15 FPS, expect ~1 identity switch per 500 frames (~33 seconds per person)
- For 60-second violations, meaningful probability of mid-violation identity switch
- **Mitigations (all mandatory):**
  1. Grace period: if track lost for <30 frames (2 seconds), timer pauses, does NOT reset
  2. Zone-level occupancy fallback: "any person in zone > N seconds" rather than per-person
  3. Conservative thresholds: alert at 45 seconds for a 60-second policy rule
  4. Workers in identical uniforms defeat ReID — use zone-level logic, not per-person tracking

### Layer 3: Temporal Verification (frame persistence + timers)

**Applies to all temporal use cases + fire/smoke false positive reduction.**

**Fire/smoke temporal filter:**
- Require detection in 3-5 consecutive frames before alerting
- Zone-based sensitivity: higher confidence threshold near welding stations
- Background subtraction: reject stationary flame-like objects

**Duration-based alerts:**

| Use Case | Duration Threshold | Timer Type |
|---|---|---|
| 20: Catwalk waiting | > 1 minute | Zone occupancy timer |
| 21: Vertical door red zone | >= 3 seconds | Zone occupancy timer |
| 26: Under suspended load (power tong) | >= 4 seconds | Intersection timer (person bbox + fall zone) |
| 27: Under suspended load (manual tong) | >= 4 seconds | Intersection timer |
| 30: Covered/dirty camera | >= 10 seconds | Frame-level classification timer |

**Speed estimation (use case 12):**
- Track vehicle across frames via OC-SORT
- Compute pixel displacement per frame
- Convert to real-world speed via homography calibration matrix
- Alert when speed exceeds configured threshold

---

## Revised Architecture Diagram

```
+---------------------------------------------------+
|          Camera Feeds (RTSP, 4-16 streams)         |
+-------------------------+-------------------------+
                          |
              +-----------v-----------+
              |   NVIDIA DeepStream   |    Hardware-accelerated decode,
              |   (camera routing)    |    batching, model routing
              +--+-------+-------+---+
                 |       |       |
        +--------v--+ +--v------v--------+
        | Model 1:  | | Model 2:        |
        | PPE Det.  | | Hazard Det.     |
        | YOLOv8m   | | YOLOv8m         |
        | (person,  | | (fire, smoke)   |
        |  helmet,  | |                 |
        |  vest,    | | + temporal      |
        |  gloves,  | |   verification  |
        |  etc.)    | |   (3-5 frames)  |
        +-----+-----+ +--------+--------+
              |                 |
              |    +------------v-----------+
              |    | Model 3: Machinery     |
              |    | YOLOv8m (crane, pipe,  |
              |    |  tong, vehicle, load)  |
              |    +------------+-----------+
              |                 |
    +---------v---------+      |
    | Model 4: Pose     |      |
    | YOLOv8m-pose      |      |
    | (17 keypoints)    |      |
    | triggered per     |      |
    | detected person   |      |
    +--------+----------+      |
             |                 |
    +--------v---------+  +----v-----------+
    | Layer 1:         |  | Layer 2:       |
    | Zone Engine      |  | OC-SORT        |
    | (polygon math,   |  | Tracker        |
    | Shapely/         |  | (identity,     |
    |  supervision)    |  |  duration)     |
    +--------+---------+  +----+-----------+
             |                 |
             +--------+--------+
                      |
             +--------v---------+
             | Layer 3:         |
             | Temporal Filter  |
             | (frame persist,  |
             |  duration timer, |
             |  speed calc)     |
             +---------+--------+
                       |
              +--------v---------+
              | Model 5: VLM     |
              | Qwen-2.5-VL 7B  |
              | (housekeeping    |
              |  ONLY, human     |
              |  review required)|
              +------------------+
```

---

## Model Summary

| Component | Type | Size | Training | GPU Memory | Notes |
|-----------|------|------|----------|------------|-------|
| PPE Detector | YOLOv8m | 25.9M params | Custom (SH17 + CHV + Roboflow) | ~2 GB | Two-stage recommended for gloves/harness |
| Hazard Detector | YOLOv8m | 25.9M params | Custom (D-Fire + MS-FSDB + industrial negatives) | ~2 GB | MUST have temporal verification layer |
| Machinery Detector | YOLOv8m | 25.9M params | Custom (industrial equipment) | ~2 GB | Crane, pipe, tong, elevator, vehicle |
| Pose Estimator | YOLOv8m-pose | ~26M params | Pretrained (no training) | ~2 GB | Triggered per detected person |
| Scene VLM | Qwen-2.5-VL 7B | 7B params | No training | ~6 GB | Housekeeping only, human review mandatory |
| OC-SORT | Algorithm | N/A | No training | CPU only | Hundreds of FPS on CPU |
| Zone Engine | Logic | N/A | No training | CPU only | Shapely point-in-polygon |
| Temporal Filter | Logic | N/A | No training | CPU only | Frame persistence + duration timers |

**Total GPU memory (all models loaded):** ~14 GB
**Minimum hardware:** Jetson AGX Orin 64GB or server with RTX 3090/4090

---

## Edge Deployment Architecture

### Hardware recommendation

| Platform | TOPS | Models Supported | FPS (total) | Use Case |
|---|---|---|---|---|
| **Jetson AGX Orin 64GB** | 275 | 3-5 concurrent | 60-120 (INT8) | Per-wellhead / per-rig |
| Jetson Orin NX 16GB | 100 | 2-3 concurrent | 15-30 | Budget / less critical |
| Hailo-8 | 26 | 1 model only | 55 (YOLOv8s) | Single-purpose camera |

### Production pipeline: NVIDIA DeepStream

- GStreamer-based: hardware-accelerated NVDEC (decode) + nvstreammux (batch) + nvinfer (TensorRT)
- **6 camera streams use only 16.5% CPU** on Jetson (decode and inference on dedicated hardware)
- Sub-30ms end-to-end latency documented by NVIDIA
- Camera-to-model routing: config-driven, no code changes to reroute cameras
- DLA offloading: AGX Orin has 2x NVDLA v2.0 — run 2 models on DLA + others on GPU

### Model optimization

- Export: PyTorch -> ONNX -> TensorRT FP16/INT8
- TensorRT speedup: 2-5x (FP16), 3-7x (INT8) over PyTorch
- **INT8 caution for PPE:** Direct PTQ drops recall (model becomes conservative, misses violations).
  Use Quantization-Aware Training (QAT) instead — maintains recall with most of INT8 speed benefit.
- Engine files are device-specific — must rebuild on target Jetson

### Multi-camera routing

Not every camera needs every model. DeepStream `deepstream_parallel_inference_app` routes by source-id:
- Cameras 0-3 (rig floor): PPE + Machinery + Pose + Zone Engine
- Cameras 4-7 (crane area): PPE + Machinery (suspended load) + Tracker
- Cameras 8-11 (perimeter): PPE + Hazard (fire/smoke) only
- Camera 12 (entry checkpoint): PPE only (close-range, high-res for gloves/harness)

---

## Risk Register

### HIGH RISK — will cause production failures if not addressed

| Risk | Impact | Mitigation |
|---|---|---|
| Gloves detection unreliable at distance | Missed PPE violations, compliance failure | Checkpoint cameras (close-range), pose-guided ROI crop |
| Fire/smoke false positives from welding | Alert fatigue, system distrust | Zone-based sensitivity + temporal verification (3-5 frames) |
| Harness confused with clothing folds | False compliance, safety risk | Close-range cameras only, pose-estimation integration |
| Identity switches reset duration timers | Missed dwell-time violations | Grace period + zone-level occupancy fallback |
| Housekeeping has no objective standard | Inconsistent enforcement | Human review mandatory, VLM flags only |

### MEDIUM RISK — degrades accuracy but not fatal

| Risk | Impact | Mitigation |
|---|---|---|
| Helmet color degrades >20m | Wrong role identification | High-res cameras in color-critical zones |
| Improper coverall is unsolved | Low detection accuracy | Frame as coverage % via segmentation, not binary |
| Speed estimation needs calibration | Inaccurate speed readings | Homography calibration per camera (8+ landmarks) |
| INT8 quantization drops PPE recall | Missed violations | Use QAT, not PTQ |

### LOW RISK — known limitations, acceptable

| Risk | Impact | Mitigation |
|---|---|---|
| Fog/haze detection is simple metrics | Less nuanced than ML | Sufficient for "poor visibility" flag |
| Crane zone is static, not dynamic | Less precise exclusion zone | Acceptable for fixed cranes; dynamic needed only for mobile cranes |
| 3-point contact has no off-the-shelf model | Custom logic needed | Geometric analysis on pose keypoints — validated in research |

---

## YOLO Version Guidance (2026)

The team should be aware of newer alternatives before committing to YOLOv8:

| Model | When to Use | Notes |
|---|---|---|
| **YOLOv8m** | Default choice for this project | Proven, large ecosystem, Ultralytics supported |
| **YOLO11m** | Drop-in upgrade | 22% fewer params than YOLOv8m, same or better accuracy |
| **RF-DETR** | If GPU is available | 58% fewer false positives than YOLO, 60.5 mAP COCO SOTA. NOT viable on CPU (>1s/image). |
| **YOLO26n** | Edge/Jetson nano tier | NMS-free, lower latency than YOLOv8n on edge |
| **EFA-YOLO** | Fire/smoke on extreme edge | 1.4M params, 22ms on CPU. Purpose-built for fire. |

**Recommendation:** Start with YOLOv8m for all 3 custom models. Migrating to YOLO11m later is
trivial (change the weights string). RF-DETR is worth evaluating if GPU is guaranteed.

---

## Implementation Phases

### Phase 1 — PPE + Person Detection (use cases 1-4, 13, 17, 18)
- Train PPE detector (YOLOv8m) on SH17 + CHV datasets
- Implement two-stage pipeline for gloves/harness (detect person -> classify PPE per crop)
- Helmet color detection (color-as-class approach)
- Worker gathering (person count >= 4)
- **Checkpoint:** mAP@50 >= 80% for helmet/vest, >= 65% for gloves, >= 70% for harness

### Phase 2 — Fire/Smoke + Temporal Verification (use cases 5, 8, 30)
- Train Hazard detector (YOLOv8m) on D-Fire + MS-FSDB
- Add industrial negatives (welding, steam, exhaust from deployment site)
- Implement temporal verification layer (3-5 frame persistence)
- Zone-based sensitivity configuration (welding zones get higher threshold)
- Covered camera detection + 10-second timer
- **Checkpoint:** <5% false positive rate with temporal filtering

### Phase 3 — Zone Engine + Tracker (use cases 9, 11, 16, 19, 20, 21, 28)
- Build polygon zone configuration UI (draw zones on camera snapshots)
- Integrate OC-SORT tracker
- Duration-based violation timers with grace period
- Camera calibration tool (homography for speed estimation)
- **Checkpoint:** Zone violations detected within 3 seconds of entry

### Phase 4 — Machinery + Suspended Load (use cases 12, 15, 23, 24, 26, 27, 31)
- Train Machinery detector (YOLOv8m)
- Implement suspended load fall zone (cone projection below detected load)
- Speed estimation via tracker + homography
- Line-of-fire corridors (static polygon per equipment path)
- **Checkpoint:** Suspended load detection >= 90% precision

### Phase 5 — Pose Analysis (use cases 6, 14, 22, 25, 29)
- Integrate YOLOv8m-pose (pretrained, no training)
- 3-point contact logic (keypoints near ladder/handrail bbox)
- Hands near pinch points (hand keypoints in danger zone polygon)
- Unsafe stair descent (body orientation analysis)
- **Checkpoint:** 3-point contact detection >= 85% accuracy in controlled test

### Phase 6 — Scene Understanding + Edge Deployment (use case 7, 10)
- Poor visibility: Laplacian variance + histogram spread (no ML)
- Housekeeping: VLM-assisted flagging with human review
- DeepStream pipeline integration for production edge deployment
- TensorRT export + QAT for INT8 optimization
- Multi-camera routing configuration
- **Checkpoint:** Full pipeline running on Jetson AGX Orin, 4+ cameras, <100ms latency

---

## Cognecto Team Status (from spreadsheet)

| Owner | Use Cases Assigned |
|-------|--------------------|
| Divyani | 2, 3, 5, 7, 8 |
| Lakshman | 4, 6, 18 |
| Unassigned | All others |

Use cases marked "Done" by Cognecto: 1, 4 (vest only — harness pending)
Use cases marked "Y" (in progress): 2, 3, 5, 6, 7, 8, 9, 12, 15, 17, 18, 19, 30
Use cases marked "No" (not understood): 10, 13, 14, 15, 16, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31

---

## Research Sources

### Production Systems
- Voxel AI: hybrid cloud, 95%+ accuracy, 50M images processed via Lightly.ai
- Intenseye Sentinel: edge hardware (Jetson Orin NX), 50+ safety indicators, vision-only 3D pose
- Detect Technologies T-Pulse: 100+ sites (Shell, Exxon, Reliance), zone monitoring
- viAct: danger zone detection, machine-human collision
- Agmis: real-world PPE deployment learnings, site-specific fine-tuning required

### Key Papers
- Cogent Engineering 2024: YOLOv8 PPE comparative study (CHV dataset, 91.7% mAP)
- SH17 (arXiv 2024): 17-class PPE dataset, 8,099 images, manufacturing
- Nature 2025: YOLOv10 PPE, 85.7% mAP@50
- D-Fire: 21K images, CC0 license, fire/smoke benchmark
- MS-FSDB (PRCV 2024): 12,586 images, best generalization benchmark
- EFA-YOLO (arXiv 2024): 1.4M params fire detector, 22ms CPU
- Nature 2025: monocular speed estimation, 97.6% average accuracy
- Cambridge Core 2025: VLMs as safety inspectors — "fully automated unrealistic today"
- SPE: computer vision line-of-fire detection in oil & gas
- ScienceDirect Safety Science 2022: suspended load fall zone detection (94% precision)

### Edge Deployment
- NVIDIA DeepStream: production multi-camera pipeline, sub-30ms latency
- Jetson AGX Orin: 275 TOPS, 3-5 models concurrent, DLA offloading
- TensorRT: 3-7x speedup with INT8, QAT recommended for safety-critical models
- Hailo-8: 10.4 TOPS/Watt, single-model only

### Tracking
- OC-SORT (CVPR 2023): observation-centric, hundreds FPS on CPU, best occlusion handling/compute ratio
- BoT-SORT: +3.0 IDF1 over ByteTrack, requires appearance embeddings
- ByteTrack: fastest, sufficient for zone-level occupancy
