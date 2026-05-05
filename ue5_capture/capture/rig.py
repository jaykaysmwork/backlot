"""CaptureRig — multi-modal synchronous SceneCapture2D bundle.

Owns N ``SceneCapture2D`` actors (one per modality) sharing a world pose.
All captures fire within a single tick via ``capture_all()``; ``export_all()``
writes files to a frame directory. Deterministic — no async pose-drift.

Why synchronous SceneCapture2D instead of ``take_high_res_screenshot``:
``take_high_res_screenshot`` is async; when capturing many modalities at
many poses, screenshot delivery can lag the camera move by one tick and
produce frames captured from the wrong pose. SceneCapture2D completes
synchronously per ``capture_scene()`` call.
"""

from __future__ import annotations

import time
from typing import Iterable, List

import unreal

from .._unreal_helpers import make_rotator
from .modalities import Modality, resolve_enum


class CaptureRig:
    """Multi-modal capture bundle owning its own SceneCapture2D actors."""

    def __init__(
        self,
        width: int,
        height: int,
        fov: float,
        modalities: Iterable[Modality],
        indirect_light_boost: float = 3.0,
        exposure_bias: float = 0.0,
    ) -> None:
        self.width = width
        self.height = height
        self.fov = fov

        self._editor_actor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        self._ue_editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        self._world = self._ue_editor.get_editor_world()

        # name → (actor, render target, extension)
        self._slots: "dict[str, tuple]" = {}

        for mod in modalities:
            src_enum = resolve_enum(unreal.SceneCaptureSource, *mod.source_names)
            fmt_enum = resolve_enum(unreal.TextureRenderTargetFormat, *mod.format_names)
            if src_enum is None or fmt_enum is None:
                print(
                    f"[rig] SKIP '{mod.name}' — enum lookup failed "
                    f"(src={mod.source_names} fmt={mod.format_names})"
                )
                continue

            rt = unreal.RenderingLibrary.create_render_target2d(
                self._world, width, height, fmt_enum
            )
            rt.set_editor_property("target_gamma", mod.target_gamma)

            actor = self._editor_actor.spawn_actor_from_class(
                unreal.SceneCapture2D,
                unreal.Vector(0.0, 0.0, 0.0),
                make_rotator(0.0, 0.0, 0.0),
            )
            actor.set_actor_label(f"_capture_rig_{mod.name}")

            comp = actor.capture_component2d
            comp.set_editor_property("capture_source", src_enum)
            comp.set_editor_property("texture_target", rt)
            comp.set_editor_property("fov_angle", fov)
            comp.set_editor_property("capture_every_frame", False)
            comp.set_editor_property("capture_on_movement", False)

            # Lumen GI is temporal — without persistent state each capture
            # starts from scratch and misses accumulated indirect lighting.
            try:
                comp.set_editor_property("always_persist_rendering_state", True)
            except Exception:
                pass

            if mod.name == "rgb":
                self._configure_lighting(comp, indirect_light_boost, exposure_bias)

            self._slots[mod.name] = (actor, rt, mod.extension)
            print(
                f"[rig] Created '{mod.name}' "
                f"({mod.source_names[0]}, {mod.format_names[0]})"
            )

    @staticmethod
    def _configure_lighting(comp, indirect_light_boost: float = 3.0, exposure_bias: float = 0.0) -> None:
        """Enable Lumen GI show flags + lighting adjustments on RGB."""
        for flag in ("GlobalIllumination", "LumenGlobalIllumination", "IndirectLighting"):
            try:
                comp.show_flag_settings.append(
                    unreal.EngineShowFlagsSetting(show_flag_name=flag, enabled=True)
                )
            except Exception:
                pass

        try:
            pp = comp.get_editor_property("post_process_settings")
            pp.set_editor_property("override_indirect_lighting_intensity", True)
            pp.set_editor_property("indirect_lighting_intensity", indirect_light_boost)
            if exposure_bias != 0.0:
                pp.set_editor_property("override_auto_exposure_bias", True)
                pp.set_editor_property("auto_exposure_bias", exposure_bias)
            comp.set_editor_property("post_process_settings", pp)
            comp.set_editor_property("post_process_blend_weight", 1.0)
            msg = f"[rig] RGB: indirect_lighting ×{indirect_light_boost}"
            if exposure_bias != 0.0:
                msg += f", exposure_bias {exposure_bias:+.1f}"
            print(msg)
        except Exception as e:
            print(f"[rig] RGB post-process config partial: {e}")

    @property
    def modality_names(self) -> List[str]:
        return list(self._slots.keys())

    def move_to(self, location: "unreal.Vector", rotation: "unreal.Rotator") -> None:
        """Move every capture actor to the same world pose."""
        for actor, _, _ in self._slots.values():
            actor.set_actor_location_and_rotation(location, rotation, False, False)

    def capture_all(self) -> float:
        """Trigger ``capture_scene()`` on every slot (synchronous). Returns ms elapsed."""
        t0 = time.perf_counter()
        for actor, _, _ in self._slots.values():
            actor.capture_component2d.capture_scene()
        return (time.perf_counter() - t0) * 1000.0

    def export_all(self, frame_dir: str) -> dict:
        """Export every render target to ``frame_dir/<name>.<ext>``.

        Returns a map ``name → True/False`` recording per-modality success;
        consumed by telemetry + quality report.
        """
        results = {}
        for name, (_, rt, ext) in self._slots.items():
            filename = f"{name}.{ext}"
            try:
                unreal.RenderingLibrary.export_render_target(
                    self._world, rt, frame_dir, filename
                )
                results[name] = True
            except Exception as e:
                print(f"  [export] FAILED {name}: {e}")
                results[name] = False
        return results

    def cleanup(self) -> None:
        """Destroy all spawned actors; safe to call multiple times."""
        for name, (actor, _, _) in self._slots.items():
            try:
                self._editor_actor.destroy_actor(actor)
            except Exception:
                pass
        print(f"[rig] Cleaned up {len(self._slots)} capture actors")
        self._slots.clear()
