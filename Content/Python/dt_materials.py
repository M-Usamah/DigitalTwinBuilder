"""Colored materials that stay visible in Lit and Unlit (not washed-out white)."""

from __future__ import annotations

import unreal

MAT_DIR = "/Game/DigitalTwin/Materials"


def _linear(rgb, a=1.0):
    r, g, b = [max(0.0, min(1.0, float(c))) for c in rgb[:3]]
    return unreal.LinearColor(r, g, b, float(a))


def _ensure_dir(path: str):
    try:
        if not unreal.EditorAssetLibrary.does_directory_exist(path):
            unreal.EditorAssetLibrary.make_directory(path)
    except Exception:
        try:
            unreal.EditorAssetLibrary.make_directory(path)
        except Exception:
            pass


def _make_color_material(name: str, rgb) -> object:
    """Unlit material: base + emissive = furniture color so it never goes white."""
    asset_path = "{}/{}".format(MAT_DIR, name)
    if unreal.EditorAssetLibrary.does_asset_exist(asset_path):
        mat = unreal.EditorAssetLibrary.load_asset(asset_path)
        if mat is not None:
            return mat

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    factory = unreal.MaterialFactoryNew()
    mat = asset_tools.create_asset(name, MAT_DIR, unreal.Material, factory)
    if mat is None:
        return None

    color = _linear(rgb)
    try:
        mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    except Exception:
        pass

    try:
        node = unreal.MaterialEditingLibrary.create_material_expression(
            mat, unreal.MaterialExpressionConstant3Vector, -350, 0
        )
        try:
            node.set_editor_property("constant", color)
        except Exception:
            try:
                node.constant = color
            except Exception:
                pass
        unreal.MaterialEditingLibrary.connect_material_property(
            node, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR
        )
        try:
            unreal.MaterialEditingLibrary.connect_material_property(
                node, "", unreal.MaterialProperty.MP_BASE_COLOR
            )
        except Exception:
            pass
        unreal.MaterialEditingLibrary.layout_material_expressions(mat)
        unreal.MaterialEditingLibrary.recompile_material(mat)
        unreal.EditorAssetLibrary.save_loaded_asset(mat)
    except Exception as exc:
        unreal.log_warning("[DigitalTwin] Material graph failed ({}): {}".format(name, exc))
    return mat


def color_material(rgb) -> object:
    _ensure_dir(MAT_DIR)
    r, g, b = [max(0.0, min(1.0, float(c))) for c in (rgb or [0.75, 0.75, 0.75])[:3]]
    name = "M_DTCol_{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))
    return _make_color_material(name, (r, g, b))


def apply_color(actor, rgb) -> bool:
    mat = color_material(rgb)
    if mat is None or actor is None:
        return False
    try:
        smc = getattr(actor, "static_mesh_component", None)
        if smc is None:
            smc = actor.get_component_by_class(unreal.StaticMeshComponent)
        if smc is None:
            return False
        try:
            if hasattr(unreal, "ComponentMobility"):
                smc.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        except Exception:
            pass
        ok = False
        for slot in range(8):
            try:
                smc.set_material(slot, mat)
                ok = True
            except Exception:
                break
        try:
            smc.set_editor_property("override_materials", [mat])
            ok = True
        except Exception:
            pass
        return ok
    except Exception as exc:
        unreal.log_warning("[DigitalTwin] apply_color failed: {}".format(exc))
        return False
