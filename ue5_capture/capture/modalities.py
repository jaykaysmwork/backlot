"""Modality table + UE enum-name fallback.

A ``Modality`` binds a file name + extension to a ``SceneCaptureSource`` +
``TextureRenderTargetFormat`` pair. ``resolve_enum`` tries multiple candidate
names because UE Python enum naming varies across minor versions — some have
``SCS_*`` prefixes, others expose the bare name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import unreal


@dataclass(frozen=True)
class Modality:
    """A single capture target.

    ``target_gamma = 1.0`` keeps output in linear space (no sRGB transform).
    """

    name: str
    source_names: Tuple[str, ...]
    format_names: Tuple[str, ...]
    extension: str
    target_gamma: float = 1.0


def resolve_enum(enum_cls, *candidate_names: str):
    """Return the first candidate attribute that exists on ``enum_cls``, else None.

    Also tries the stripped-prefix form (``SCS_X`` → ``X``).
    """
    for n in candidate_names:
        if hasattr(enum_cls, n):
            return getattr(enum_cls, n)
        if "_" in n:
            bare = n.split("_", 1)[1]
            if hasattr(enum_cls, bare):
                return getattr(enum_cls, bare)
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  Native UE5 modalities (4)
#
#  Note: depth.png and depth.exr are NOT UE-native — they're produced post-
#  capture by convert_depth.py from depth_tmp.exr. All float modalities use
#  EXR as the intermediate format. convert_depth.py normalizes depth_tmp.exr
#  into depth.exr (float16 ground truth) + depth.png (grayscale for web).
# ─────────────────────────────────────────────────────────────────────────────

NATIVE_MODALITIES: Tuple[Modality, ...] = (
    Modality(
        name="rgb",
        source_names=("SCS_FINAL_COLOR_LDR",),
        format_names=("RTF_RGBA8",),
        extension="png",
    ),
    Modality(
        name="depth_tmp",
        source_names=("SCS_SCENE_DEPTH",),
        format_names=("RTF_RGBA16F",),
        extension="exr",
    ),
    Modality(
        name="normal",
        source_names=("SCS_NORMAL",),
        format_names=("RTF_RGBA16F",),
        extension="exr",
    ),
    Modality(
        name="base_color",
        source_names=("SCS_BASE_COLOR",),
        format_names=("RTF_RGBA16F",),
        extension="exr",
    ),
)
