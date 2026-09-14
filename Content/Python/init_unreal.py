"""Register Digital Twin Builder under Tools when the editor starts."""

import os

import unreal

MENU_OWNER = "DigitalTwinBuilder"
ENTRY_NAME = "BuildDigitalTwin"
_PLUGIN_ENTRY = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "digital_twin_builder.py"
).replace("\\", "/")
PYTHON_COMMAND = (
    "import importlib.util, sys; "
    "p = r'{path}'; "
    "spec = importlib.util.spec_from_file_location('dtb_plugin_entry', p); "
    "mod = importlib.util.module_from_spec(spec); "
    "sys.modules['dtb_plugin_entry'] = mod; "
    "spec.loader.exec_module(mod); "
    "mod.run()"
).format(path=_PLUGIN_ENTRY)


def register_menus():
    menus = unreal.ToolMenus.get()
    tools_menu = menus.extend_menu("LevelEditor.MainMenu.Tools")
    tools_menu.add_section(MENU_OWNER, "Digital Twin Builder")

    entry = unreal.ToolMenuEntry(
        name=ENTRY_NAME,
        type=unreal.MultiBlockType.MENU_ENTRY,
        insert_position=unreal.ToolMenuInsert("", unreal.ToolMenuInsertType.DEFAULT),
    )
    entry.set_label("Build Digital Twin from Images/Video...")
    entry.set_tool_tip(
        "Pick images or a video, preprocess (detect + layout), and spawn the twin in the level. "
        "Live progress appears in Output Log."
    )
    entry.set_string_command(
        unreal.ToolMenuStringCommandType.PYTHON,
        unreal.Name(""),
        PYTHON_COMMAND,
    )
    tools_menu.add_menu_entry(MENU_OWNER, entry)
    menus.refresh_all_widgets()
    unreal.log("Digital Twin Builder: Tools menu registered.")


register_menus()

