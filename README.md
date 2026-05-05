<div align="center">

# Backlot

**End-to-end synthetic data pipeline for Unreal Engine 5**

Automated multi-modal capture · PostGIS spatial indexing · Interactive web explorer

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![UE5](https://img.shields.io/badge/Unreal_Engine-5.5+-0E1128?logo=unrealengine&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL_+_PostGIS-16-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker_Compose-Ready-2496ED?logo=docker&logoColor=white)

</div>

---

### Capture Output

<table>
<tr>
<td align="center"><strong>RGB</strong></td>
<td align="center"><strong>Depth</strong></td>
<td align="center"><strong>Normal</strong></td>
<td align="center"><strong>Base Color</strong></td>
</tr>
<tr>
<td><img src="docs/images/rgb.png" width="220"/></td>
<td><img src="docs/images/depth.png" width="220"/></td>
<td><img src="docs/images/normal.png" width="220"/></td>
<td><img src="docs/images/base_color.png" width="220"/></td>
</tr>
</table>

`4 modalities × 30 frames per session, fully automated`

---

### Pipeline

```mermaid
graph LR
    subgraph UE5["Unreal Engine 5"]
        A["SceneCapture2D\n4 modalities"] --> B["convert_depth.py\nEXR → PNG"]
    end

    B --> C["capture_output/"]

    subgraph PostCapture["Post-Capture"]
        C --> E["ingest.py\nJSON → PostgreSQL"]
    end

    subgraph Server["Docker Stack"]
        E --> F[("PostgreSQL 16\n+ PostGIS")]
        F --> G["FastAPI\nREST API"]
        G --> H["Next.js 16\nExplorer UI"]
    end

    style UE5 fill:#1a1a2e,stroke:#4a4a6a,color:#e0e0e0
    style PostCapture fill:#16213e,stroke:#4a4a6a,color:#e0e0e0
    style Server fill:#0f3460,stroke:#4a4a6a,color:#e0e0e0
```

---

### Features

- **Multi-pass capture engine** — RGB, depth (float16 EXR), world-space normals, base color, and per-actor metadata from any UE5 scene. 8 camera trajectory modes including Fibonacci hemisphere, Catmull-Rom spline, and spatial random walk.

- **PostGIS spatial indexing** — Camera positions stored as `geometry(PointZ)` with GiST index. Query frames by 3D proximity using `ST_3DDWithin` — both via API and the frontend filter panel.

- **Interactive web explorer** — Browse sessions, filter frames by actor class / camera position / spatial proximity, inspect per-frame modalities with bbox overlay, and visualize full camera trajectories in a 3D viewer (React Three Fiber).

- **One-click UE5 editor menu** — Editor menu integration via UE5's `ToolMenus` API. Mode selection, presets, and config editing without touching the Python console. Installed globally so every UE5 project picks it up on startup.

---

## Get Running

> **You need:** Docker 24+ with Compose v2. That's it.
>
> The repo ships with `sample_data/` so the demo works immediately after clone.
> Python 3.11+ and UE5 are only needed if you're capturing new scenes.

**Three commands:**

```bash
git clone <repo-url> backlot && cd backlot
docker compose up -d
docker compose run --rm ingest
```

**Then open:** http://localhost:3000

> **Using your own captures?** Drop them into `capture_output/` and re-run — auto-detected on startup.

| | URL | What |
|---|-----|------|
| UI | http://localhost:3000 | Session browser, frame filters, 3D viewer |
| API | http://localhost:8000/docs | Swagger / OpenAPI |
| DB | `postgres://admin:password@localhost:5432/backlot` | Direct access |

```bash
docker compose down       # stop
docker compose down -v    # stop + wipe DB
```

### UE5 Editor Menu (optional)

If you're capturing new scenes, install the editor menu for one-click capture:

```bash
python scripts/install_editor_menu.py
```

Restart UE5 — a **Backlot** menu appears in the menu bar. Works globally across all UE5 projects.

| Menu Item | What it does |
|-----------|-------------|
| **Current Config** | Show active settings in a dialog |
| **Edit Config File...** | Open `editor_config.json` in your editor |
| **Capture Single Scene** | Capture current level with confirmation |
| **Batch Capture** | Auto-detect rooms and capture each one |
| **Mode →** | Switch camera path (orbit, local_orbit, look_around, multi_look, walk_through, sphere_interior, random_walk, spline) |
| **Presets →** | Quick Test (5), Standard (20), High Coverage (50 frames) |

Config only shows parameters relevant to the selected mode — e.g. `radius_cm` appears for `local_orbit` but not `look_around`.

```bash
python scripts/install_editor_menu.py --uninstall  # remove
```

---

## Capture (UE5)

Two modes, both run from the UE5 Python console.

### Single Scene

```python
CAPTURE_N_FRAMES = 30          # default: 20
CAPTURE_MODE = "orbit"         # see mode table below
exec(open("/path/to/backlot/ue5_capture/capture.py").read())
```

### Batch (auto-detect rooms)

```python
BATCH_N_FRAMES = 30            # per room
BATCH_MODE = "multi_look"      # mode per room
BATCH_DRY_RUN = True           # preview rooms first, no capture
exec(open("/path/to/backlot/ue5_capture/capture_batch.py").read())
```

### Camera Modes

| Mode | What it does | Key param |
|------|-------------|-----------|
| `orbit` | Fibonacci hemisphere around scene center | — |
| `local_orbit` | Same, at custom radius | `CAPTURE_RADIUS` (400cm) |
| `look_around` | Fixed position, rotating view | — |
| `multi_look` | Multiple viewpoints, each sweeping a direction arc | `CAPTURE_SPREAD` (200cm) |
| `walk_through` | Linear walk along viewport heading | `CAPTURE_WALK_DISTANCE` (800cm) |
| `sphere_interior` | Inward-looking poses on sphere surface | `CAPTURE_RADIUS` |
| `random_walk` | Random steps, seeded RNG | `CAPTURE_STEP_CM` (150cm) |
| `spline` | Catmull-Rom through random control points | `CAPTURE_SPLINE_POINTS` (6) |

### All Parameters

**capture.py** — set as globals before `exec()`:

| Param | Default | |
|-------|---------|---|
| `CAPTURE_N_FRAMES` | `20` | Frame count |
| `CAPTURE_MODE` | `"orbit"` | Camera path |
| `CAPTURE_LABEL` | `None` | Sub-folder name (e.g. `"main_hall"`) |
| `CAPTURE_RADIUS` | `400.0` | Orbit radius in cm |
| `CAPTURE_INDIRECT_LIGHT` | `3.0` | Indirect lighting multiplier |
| `CAPTURE_EXPOSURE_BIAS` | `0.0` | EV offset (+1 = 2x brighter) |
| `CAPTURE_SKIP_CLASSES` | *(defaults)* | Actor classes to exclude |
| `CAPTURE_SKIP_PREFIXES` | *(defaults)* | Class name prefixes to exclude |

**capture_batch.py** — additional params:

| Param | Default | |
|-------|---------|---|
| `BATCH_MODE` | `"multi_look"` | Camera mode per room |
| `BATCH_N_FRAMES` | `20` | Frames per room |
| `BATCH_CLUSTER_R` | `800.0` | Clustering radius (cm) |
| `BATCH_MIN_ACTORS` | `3` | Min actors to form a room |
| `BATCH_DRY_RUN` | `False` | Preview only |

---

## Post-Capture

### Ingestion

```bash
python -m ingestion.ingest capture_output/                   # all sessions
python -m ingestion.ingest capture_output/<project>/<scene>  # one session
```

Idempotent — safe to re-run.

---

## What Gets Captured

```
capture_output/<project>/<scene>/
├── session.json                   metadata + config
└── frames/frame_000/
    ├── rgb.png                    final color (1920x1080)
    ├── depth.png                  8-bit normalized
    ├── depth.exr                  float16 cm (ML ground truth)
    ├── normal.exr / normal.png    world-space normals
    ├── base_color.exr / .png      albedo
    ├── camera.json                pose + intrinsics
    └── objects.json               actors, 3D bounds, 2D bbox
```

---

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/sessions` | All sessions |
| `GET /api/sessions/{id}` | Session + unique classes |
| `GET /api/frames?session_id=&class_filter=&visible_only=` | Filtered frames |
| `GET /api/frames/{id}` | Frame + objects |
| `GET /api/frames/near?x=&y=&z=&radius_cm=` | PostGIS spatial query |

---

## Stack

| | |
|---|---|
| **Capture** | UE5 5.7, SceneCapture2D, 4 modalities, 8 camera modes |
| **Database** | PostgreSQL 16 + PostGIS 3.5, GiST spatial index |
| **Backend** | FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| **Frontend** | Next.js 16, React 19, Tailwind v4, Framer Motion, React Three Fiber |

---

## Dev Setup (without Docker)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d postgres
uvicorn backend.main:app --reload
cd frontend && npm install && npm run dev
```
