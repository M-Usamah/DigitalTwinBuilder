"""Create Digital Twin level, spawn actors from unreal_scene.json, frame the view."""

from __future__ import annotations

import json
import os

import unreal

from dt_paths import norm
from dt_progress import log_line
from dt_materials import apply_color

CONTENT_MAPS_DIR = "/Game/DigitalTwin/Maps"


def plotly_to_unreal(loc_xyz, yaw_deg, unit_scale: float):
    """Plotly Y-up (X,Y,Z) → Unreal Z-up (X, PlotlyZ, PlotlyY). Yaw around world up."""
    x, y_up, z = loc_xyz
    ue = unreal.Vector(float(x) * unit_scale, float(z) * unit_scale, float(y_up) * unit_scale)
    rot = unreal.Rotator(pitch=0.0, yaw=float(yaw_deg), roll=0.0)
    return ue, rot


def load_basic_mesh(shape: str):
    paths = {
        "box": "/Engine/BasicShapes/Cube.Cube",
        "cylinder": "/Engine/BasicShapes/Cylinder.Cylinder",
        "sphere": "/Engine/BasicShapes/Sphere.Sphere",
        "plane": "/Engine/BasicShapes/Plane.Plane",
    }
    asset_path = paths.get(shape, paths["box"])
    mesh = unreal.EditorAssetLibrary.load_asset(asset_path)
    if mesh is None:
        unreal.log_warning("[DigitalTwin] Failed to load mesh {}".format(asset_path))
    return mesh


def _set_static_mesh(actor, mesh) -> bool:
    try:
        smc = getattr(actor, "static_mesh_component", None)
        if smc is None:
            smc = actor.get_component_by_class(unreal.StaticMeshComponent)
        if smc is None:
            return False
        smc.set_static_mesh(mesh)
        return True
    except Exception as exc:
        unreal.log_warning("[DigitalTwin] set_static_mesh failed: {}".format(exc))
        return False


def _level_subsystem():
    try:
        return unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    except Exception:
        return None


def digital_twin_level_path(scene: str) -> str:
    return "{}/Lvl_DigitalTwin".format(CONTENT_MAPS_DIR)


def prepare_digital_twin_level(scene: str, log_file=None) -> str:
    """
    Save current map if possible, then create or load
    /Game/DigitalTwin/Maps/Lvl_DigitalTwin_<scene> and make it the active level.
    """
    level_path = digital_twin_level_path(scene)
    log_line("[DigitalTwin] Preparing level: {}".format(level_path), log_file)

    les = _level_subsystem()

    # Try not to lose the user's current map
    try:
        if les is not None and hasattr(les, "save_current_level"):
            les.save_current_level()
        elif hasattr(unreal, "EditorLevelLibrary"):
            unreal.EditorLevelLibrary.save_current_level()
    except Exception as exc:
        unreal.log_warning("[DigitalTwin] Could not save current level: {}".format(exc))

    try:
        unreal.EditorAssetLibrary.make_directory(CONTENT_MAPS_DIR)
    except Exception:
        pass

    exists = False
    try:
        exists = unreal.EditorAssetLibrary.does_asset_exist(level_path)
    except Exception:
        exists = False

    ok = False
    if exists:
        log_line("[DigitalTwin] Loading existing Digital Twin level...", log_file)
        try:
            if les is not None:
                ok = bool(les.load_level(level_path))
            if not ok and hasattr(unreal, "EditorLevelLibrary"):
                ok = bool(unreal.EditorLevelLibrary.load_level(level_path))
        except Exception as exc:
            unreal.log_warning("[DigitalTwin] load_level failed: {}".format(exc))
            ok = False
    else:
        log_line("[DigitalTwin] Creating new Digital Twin level...", log_file)
        try:
            if les is not None:
                ok = bool(les.new_level(level_path))
            if not ok and hasattr(unreal, "EditorLevelLibrary"):
                ok = bool(unreal.EditorLevelLibrary.new_level(level_path))
        except Exception as exc:
            unreal.log_warning("[DigitalTwin] new_level failed: {}".format(exc))
            ok = False

    if not ok:
        raise RuntimeError(
            "Could not create/load Digital Twin level:\n{}\n"
            "Stay in the current level and spawn there as fallback.".format(level_path)
        )

    log_line("[DigitalTwin] Active level ready: {}".format(level_path), log_file)
    return level_path


def clear_previous_twin():
    try:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        removed = 0
        for actor in list(subsystem.get_all_level_actors()):
            try:
                label = actor.get_actor_label()
            except Exception:
                label = ""
            if label.startswith("DT_"):
                subsystem.destroy_actor(actor)
                removed += 1
        if removed:
            unreal.log("[DigitalTwin] Cleared {} previous twin actor(s)".format(removed))
    except Exception as exc:
        unreal.log_warning("[DigitalTwin] Clear failed: {}".format(exc))


def _spawn_mesh_actor(subsystem, mesh, loc, rot, scale, label, folder, rgb=None):
    actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, loc, rot)
    if actor is None:
        return None
    if not _set_static_mesh(actor, mesh):
        subsystem.destroy_actor(actor)
        return None
    actor.set_actor_scale3d(scale)
    actor.set_actor_label(label)
    try:
        actor.set_folder_path(folder)
    except Exception:
        pass
    if rgb:
        if not apply_color(actor, rgb):
            unreal.log_warning("[DigitalTwin] Color failed on {}".format(label))
    return actor


def _resolve_actor_class(*candidates):
    """Resolve an actor UClass from unreal attrs or /Script paths."""
    for name in candidates:
        if not name:
            continue
        if name.startswith("/"):
            try:
                cls = unreal.load_class(None, name)
                if cls is not None:
                    return cls
            except Exception:
                pass
            continue
        try:
            cls = getattr(unreal, name, None)
            if cls is not None:
                return cls
        except Exception:
            pass
    return None


def _tag_actor(actor, label: str, folder: str):
    if actor is None:
        return
    try:
        actor.set_actor_label(label)
    except Exception:
        pass
    try:
        actor.set_folder_path(folder)
    except Exception:
        pass


def _spawn_typed_actor(subsystem, class_names, loc, rot, label, folder, log_file=None):
    cls = _resolve_actor_class(*class_names)
    if cls is None:
        log_line("[DigitalTwin] Class not found for {}".format(label), log_file)
        return None
    try:
        actor = subsystem.spawn_actor_from_class(cls, loc, rot)
    except Exception as exc:
        log_line("[DigitalTwin] Spawn {} failed: {}".format(label, exc), log_file)
        return None
    if actor is None:
        log_line("[DigitalTwin] Spawn {} returned None".format(label), log_file)
        return None
    _tag_actor(actor, label, folder)
    return actor


def _set_prop(obj, names, value):
    if obj is None:
        return False
    for name in names:
        try:
            if hasattr(obj, "set_editor_property"):
                obj.set_editor_property(name, value)
                return True
        except Exception:
            pass
        try:
            setattr(obj, name, value)
            return True
        except Exception:
            pass
    return False


def _configure_directional_light(light):
    comp = None
    try:
        comp = light.get_component_by_class(unreal.DirectionalLightComponent)
    except Exception:
        comp = getattr(light, "directional_light_component", None)
    if comp is None:
        return
    _set_prop(comp, ["intensity", "Intensity"], 4.0)
    _set_prop(comp, ["indirect_lighting_intensity", "IndirectLightingIntensity"], 1.0)
    _set_prop(comp, ["volumetric_scattering_intensity", "VolumetricScatteringIntensity"], 1.0)
    try:
        # Stationary/Movable so it lights the empty map immediately
        if hasattr(unreal, "ComponentMobility"):
            _set_prop(comp, ["mobility", "Mobility"], unreal.ComponentMobility.MOVABLE)
    except Exception:
        pass


def _configure_sky_light(sky):
    comp = None
    try:
        comp = sky.get_component_by_class(unreal.SkyLightComponent)
    except Exception:
        comp = getattr(sky, "light_component", None)
    if comp is None:
        return
    _set_prop(comp, ["intensity", "Intensity"], 1.0)
    _set_prop(comp, ["real_time_capture", "bRealTimeCapture"], True)
    try:
        if hasattr(unreal, "ComponentMobility"):
            _set_prop(comp, ["mobility", "Mobility"], unreal.ComponentMobility.MOVABLE)
    except Exception:
        pass
    try:
        if hasattr(comp, "recapture_sky"):
            comp.recapture_sky()
    except Exception:
        pass


def _configure_point_light(light, intensity=8000.0, radius=2500.0):
    comp = None
    try:
        comp = light.get_component_by_class(unreal.PointLightComponent)
    except Exception:
        comp = getattr(light, "point_light_component", None)
    if comp is None:
        return
    _set_prop(comp, ["intensity", "Intensity"], intensity)
    _set_prop(comp, ["attenuation_radius", "AttenuationRadius"], radius)
    _set_prop(comp, ["cast_shadows", "CastShadows"], True)
    try:
        if hasattr(unreal, "ComponentMobility"):
            _set_prop(comp, ["mobility", "Mobility"], unreal.ComponentMobility.MOVABLE)
    except Exception:
        pass


def _configure_post_process(volume):
    """Raise exposure so Lit mode is not pitch black in an empty map."""
    _set_prop(volume, ["unbound", "bUnbound"], True)
    settings = None
    try:
        settings = volume.get_editor_property("settings")
    except Exception:
        settings = getattr(volume, "settings", None)
    if settings is None:
        return
    _set_prop(settings, ["override_auto_exposure_min_brightness", "bOverride_AutoExposureMinBrightness"], True)
    _set_prop(settings, ["auto_exposure_min_brightness", "AutoExposureMinBrightness"], 0.8)
    _set_prop(settings, ["override_auto_exposure_max_brightness", "bOverride_AutoExposureMaxBrightness"], True)
    _set_prop(settings, ["auto_exposure_max_brightness", "AutoExposureMaxBrightness"], 1.2)
    _set_prop(settings, ["override_auto_exposure_bias", "bOverride_AutoExposureBias"], True)
    _set_prop(settings, ["auto_exposure_bias", "AutoExposureBias"], 0.0)
    try:
        volume.set_editor_property("settings", settings)
    except Exception:
        try:
            volume.settings = settings
        except Exception:
            pass


def setup_level_environment(scene: str, log_file=None):
    """Ground + strong lights + exposure so Lit viewport is not black."""
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    folder = "DigitalTwin/{}".format(scene)

    existing = {}
    for actor in subsystem.get_all_level_actors():
        try:
            label = actor.get_actor_label()
        except Exception:
            label = ""
        if label.startswith("DT_"):
            existing[label] = actor

    # Large ground under the furniture (Plane is 100x100 uu at scale 1)
    if "DT_Ground" not in existing:
        plane = load_basic_mesh("plane")
        if plane is not None:
            _spawn_mesh_actor(
                subsystem,
                plane,
                unreal.Vector(0.0, 0.0, 0.0),
                unreal.Rotator(pitch=0.0, yaw=0.0, roll=0.0),
                unreal.Vector(12.0, 12.0, 1.0),
                "DT_Ground",
                folder,
                rgb=(0.45, 0.46, 0.48),
            )
            log_line("[DigitalTwin] Added ground plane", log_file)

    # --- Lights (multiple sources so Lit is never black) ---
    if "DT_DirectionalLight" not in existing:
        light = _spawn_typed_actor(
            subsystem,
            ("DirectionalLight", "/Script/Engine.DirectionalLight"),
            unreal.Vector(200.0, -300.0, 600.0),
            unreal.Rotator(-50.0, -35.0, 0.0),
            "DT_DirectionalLight",
            folder,
            log_file,
        )
        if light is not None:
            _configure_directional_light(light)
            log_line("[DigitalTwin] Added directional light", log_file)

    if "DT_SkyLight" not in existing:
        sky = _spawn_typed_actor(
            subsystem,
            ("SkyLight", "/Script/Engine.SkyLight"),
            unreal.Vector(0.0, 0.0, 100.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            "DT_SkyLight",
            folder,
            log_file,
        )
        if sky is not None:
            _configure_sky_light(sky)
            log_line("[DigitalTwin] Added sky light", log_file)

    if "DT_FillLight" not in existing:
        fill = _spawn_typed_actor(
            subsystem,
            ("PointLight", "/Script/Engine.PointLight"),
            unreal.Vector(0.0, 0.0, 450.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            "DT_FillLight",
            folder,
            log_file,
        )
        if fill is not None:
            _configure_point_light(fill, intensity=1500.0, radius=2500.0)
            log_line("[DigitalTwin] Added fill point light", log_file)

    if "DT_KeyLight" not in existing:
        key = _spawn_typed_actor(
            subsystem,
            ("PointLight", "/Script/Engine.PointLight"),
            unreal.Vector(-250.0, -200.0, 350.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            "DT_KeyLight",
            folder,
            log_file,
        )
        if key is not None:
            _configure_point_light(key, intensity=1200.0, radius=2000.0)
            log_line("[DigitalTwin] Added key point light", log_file)

    if "DT_SkyAtmosphere" not in existing:
        atmo = _spawn_typed_actor(
            subsystem,
            ("SkyAtmosphere", "/Script/Engine.SkyAtmosphere"),
            unreal.Vector(0.0, 0.0, 0.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            "DT_SkyAtmosphere",
            folder,
            log_file,
        )
        if atmo is not None:
            log_line("[DigitalTwin] Added sky atmosphere", log_file)

    if "DT_PostProcess" not in existing:
        pp = _spawn_typed_actor(
            subsystem,
            ("PostProcessVolume", "/Script/Engine.PostProcessVolume"),
            unreal.Vector(0.0, 0.0, 100.0),
            unreal.Rotator(0.0, 0.0, 0.0),
            "DT_PostProcess",
            folder,
            log_file,
        )
        if pp is not None:
            _configure_post_process(pp)
            log_line("[DigitalTwin] Added post-process (exposure boost)", log_file)

    # Nudge editor lighting rebuild / viewport
    try:
        world = None
        if hasattr(unreal, "EditorLevelLibrary"):
            world = unreal.EditorLevelLibrary.get_editor_world()
        if world is not None:
            unreal.SystemLibrary.execute_console_command(world, "RebuildLighting")
            unreal.SystemLibrary.execute_console_command(world, "r.SkyLight.RealTimeReflectionCapture 1")
    except Exception:
        pass

    # Verify at least one light exists
    light_labels = ("DT_DirectionalLight", "DT_SkyLight", "DT_FillLight", "DT_KeyLight")
    found = []
    for actor in subsystem.get_all_level_actors():
        try:
            label = actor.get_actor_label()
        except Exception:
            continue
        if label in light_labels:
            found.append(label)
    log_line("[DigitalTwin] Lights in level: {}".format(", ".join(found) or "NONE"), log_file)
    if not found:
        log_line(
            "[DigitalTwin] WARNING: no lights spawned — switch viewport to Unlit as fallback",
            log_file,
        )


def frame_camera_on_twin(locations, log_file=None):
    """Point the perspective viewport at the twin (not the sky)."""
    if locations:
        cx = sum(v.x for v in locations) / float(len(locations))
        cy = sum(v.y for v in locations) / float(len(locations))
        cz = sum(v.z for v in locations) / float(len(locations))
    else:
        cx, cy, cz = 0.0, 0.0, 100.0

    # Stand south of the cluster, looking toward +Y (at the twin)
    cam_loc = unreal.Vector(cx, cy - 900.0, max(cz, 80.0) + 420.0)
    cam_rot = unreal.Rotator(-28.0, 90.0, 0.0)

    try:
        unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(
            cam_loc, cam_rot
        )
        log_line(
            "[DigitalTwin] Viewport framed @ ({:.0f},{:.0f},{:.0f})".format(
                cam_loc.x, cam_loc.y, cam_loc.z
            ),
            log_file,
        )
    except Exception as exc:
        unreal.log_warning("[DigitalTwin] Camera frame failed: {}".format(exc))


def save_digital_twin_level(level_path: str, log_file=None):
    les = _level_subsystem()
    try:
        if les is not None and hasattr(les, "save_current_level"):
            les.save_current_level()
        elif hasattr(unreal, "EditorLevelLibrary"):
            unreal.EditorLevelLibrary.save_current_level()
        log_line("[DigitalTwin] Level saved: {}".format(level_path), log_file)
    except Exception as exc:
        unreal.log_warning("[DigitalTwin] Save level failed: {}".format(exc))

    try:
        unreal.EditorAssetLibrary.save_asset(level_path, only_if_is_dirty=False)
    except Exception:
        pass


def _make_text(value: str):
    try:
        return unreal.Text(str(value))
    except Exception:
        return str(value)


def _apply_label_text(comp, text: str) -> bool:
    ftext = _make_text(text)
    try:
        comp.set_text(ftext)
        return True
    except Exception:
        pass
    try:
        comp.set_editor_property("text", ftext)
        return True
    except Exception:
        pass
    try:
        comp.set_text(str(text))
        return True
    except Exception:
        return False


def _spawn_label(subsystem, loc, height_cm, text, folder, actor_id, log_file=None):
    tloc = unreal.Vector(loc.x, loc.y, loc.z + max(float(height_cm), 20.0) * 0.55 + 18.0)
    try:
        text_actor = subsystem.spawn_actor_from_class(
            unreal.TextRenderActor, tloc, unreal.Rotator(pitch=0.0, yaw=180.0, roll=0.0)
        )
    except Exception as exc:
        unreal.log_warning("Label spawn failed: {}".format(exc))
        return
    if text_actor is None:
        return
    text_actor.set_actor_label("DT_{}_label".format(actor_id))
    try:
        text_actor.set_folder_path(folder)
    except Exception:
        pass
    comp = None
    try:
        comp = text_actor.get_component_by_class(unreal.TextRenderComponent)
    except Exception:
        comp = None
    if comp is None:
        comp = getattr(text_actor, "text_render", None) or getattr(
            text_actor, "text_render_component", None
        )
    if comp is None:
        log_line("[DigitalTwin] No TextRenderComponent for {}".format(text), log_file)
        return
    if not _apply_label_text(comp, text):
        log_line("[DigitalTwin] Could not set label text '{}'".format(text), log_file)
    try:
        if hasattr(comp, "set_world_size"):
            comp.set_world_size(22.0)
        else:
            comp.set_editor_property("world_size", 22.0)
    except Exception:
        pass
    try:
        gold = unreal.Color(255, 213, 106, 255)
        if hasattr(comp, "set_text_render_color"):
            comp.set_text_render_color(gold)
        else:
            comp.set_editor_property("text_render_color", gold)
    except Exception:
        pass
    try:
        if hasattr(unreal, "HorizTextAligment"):
            comp.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
    except Exception:
        pass


def spawn_scene_from_json(scene_path: str, log_file=None) -> tuple[int, str]:
    """
    Create/open Digital Twin level, spawn colored furniture parts matching Plotly,
    save + frame camera. Returns (spawned_count, level_asset_path).
    """
    scene_path = norm(scene_path)
    with open(scene_path, "r", encoding="utf-8") as f:
        doc = json.load(f)
    actors = doc.get("actors", [])
    unit = float(doc.get("unreal_unit_scale", 20.0))
    scene = doc.get("scene", "unknown")

    level_path = None
    try:
        level_path = prepare_digital_twin_level(scene, log_file)
    except Exception as exc:
        log_line(
            "[DigitalTwin] WARNING: new level failed ({}) — spawning in current level".format(exc),
            log_file,
        )
        level_path = "(current level)"

    clear_previous_twin()
    setup_level_environment(scene, log_file)

    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = 0
    locations = []
    total = max(len(actors), 1)
    folder = "DigitalTwin/{}".format(scene)

    with unreal.ScopedSlowTask(total, "Spawning Digital Twin") as slow:
        slow.make_dialog(True)
        for i, spec in enumerate(actors):
            if slow.should_cancel():
                log_line("[DigitalTwin] Spawn cancelled", log_file)
                break
            slow.enter_progress_frame(
                1, "Spawning {} ({}/{})".format(spec.get("id"), i + 1, total)
            )

            mesh = load_basic_mesh(spec.get("shape", "box"))
            if mesh is None:
                continue

            loc, rot = plotly_to_unreal(spec["location"], spec.get("yaw_deg", 0.0), unit)
            sx, sy, sz = spec.get("scale", [1, 1, 1])
            # Engine Cube/Cylinder are 100uu. scale = plotly extent * cm-per-unit / 100
            scale = unreal.Vector(
                (float(sx) * unit) / 100.0,
                (float(sz) * unit) / 100.0,
                (float(sy) * unit) / 100.0,
            )

            actor = _spawn_mesh_actor(
                subsystem,
                mesh,
                loc,
                rot,
                scale,
                "DT_{}".format(spec.get("id", "actor")),
                folder,
                rgb=spec.get("color"),
            )
            if actor is None:
                continue

            locations.append(loc)

            spawned += 1
            if spec.get("show_label") or i < 3:
                log_line(
                    "[DigitalTwin] Spawned {} @ ({:.0f},{:.0f},{:.0f})".format(
                        spec.get("id"), loc.x, loc.y, loc.z
                    ),
                    log_file,
                )

    log_line("[DigitalTwin] Spawned {} mesh part(s)".format(spawned), log_file)
    frame_camera_on_twin(locations, log_file)
    setup_level_environment(scene, log_file)

    if level_path and level_path != "(current level)":
        save_digital_twin_level(level_path, log_file)

    try:
        twin_actors = [
            a
            for a in subsystem.get_all_level_actors()
            if str(a.get_actor_label()).startswith("DT_")
            and not str(a.get_actor_label()).endswith("_label")
            and a.get_actor_label() not in ("DT_Ground", "DT_DirectionalLight", "DT_SkyLight")
        ]
        if twin_actors:
            subsystem.set_selected_level_actors(twin_actors[:1])
    except Exception:
        pass

    return spawned, level_path
