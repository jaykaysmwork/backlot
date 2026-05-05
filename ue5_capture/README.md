# ue5_capture — Capture Engine

Runs inside UE5's Python console. Produces a single-session `capture_output/`
directory containing multi-modal frames + session manifest + quality report.

## Module map

```
capture.py           Entry point (UE5 Python console)
convert_depth.py     Post-capture HDR→EXR (system Python)

mission/             Declarative capture plans
  plan.py             MissionPlan Pydantic model
  strategies.py       Orbit / Waypoints / Spline (Strategy pattern)
  compiler.py         MissionPlan → concrete Frame list
  validator.py        Post-capture coverage goal check
  llm_generator.py    Natural-language → MissionPlan (stub)

capture/             SceneCapture2D rig
  rig.py              Multi-modal synchronous bundle
  modalities.py       Modality enum + UE enum lookup fallback
  telemetry.py        Per-frame timing

annotate/            Per-frame annotation
  actors.py           Actor filter + 3D bounds + metadata
  projection.py       Camera K / E / 2D bbox projection

provenance/          Audit trail
  session.py          Immutable session manifest
  rights.py           Rights-cleared metadata scaffold

verify/              Self-check
  schema.py           Pydantic model re-exports
  quality_report.py   Schema + file integrity + content sanity

missions/            Mission plan files (Python dicts)
  hub_orbit.py
  auto_spline.py
```

## Prerequisites

- UE5 5.4+
- System Python 3.10+ with `imageio` (for HDR→EXR conversion)

> Sections below are filled in as phases land.

## How to run
(TODO P1.11)

## Design decisions
See [DESIGN.md](DESIGN.md).

## Retrospective
See [RETROSPECTIVE.md](RETROSPECTIVE.md).
