# Capture Engine — Design Notes

> Fills in through Phases P1.0 → P1.11.

## Coordinate convention

UE5 left-handed: `+X forward`, `+Y right`, `+Z up`. Units: centimeters.
Camera frame matches world frame.

## Modality matrix

| File | Source | RT format | Written by |
|------|--------|-----------|------------|
| `rgb.png` | `SCS_FINAL_COLOR_LDR` | `RTF_RGBA8` | UE5 native |
| `depth.png` | `SCS_SCENE_DEPTH` | `RTF_RGBA8` | UE5 native — spec-mandated 8-bit grayscale |
| `depth.exr` | `SCS_SCENE_DEPTH` → `depth_tmp.hdr` → imageio | `RTF_RGBA16F` intermediate | System Python (post-capture) |
| `normal.png` | `SCS_NORMAL` | `RTF_RGBA16F` | UE5 native |
| `base_color.png` | `SCS_BASE_COLOR` | `RTF_RGBA16F` | UE5 native |

## Mission DSL

(TODO P1.6)

## Why synchronous SceneCapture2D rig, not `take_high_res_screenshot`

(TODO P1.11 — document async pose-drift issue)

## Why 3D world bounds + projected 2D bbox

(TODO P1.11)
