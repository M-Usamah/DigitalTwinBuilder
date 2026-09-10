"""Register Digital Twin Builder under Tools when the editor starts."""

import unreal

MENU_OWNER = "DigitalTwinBuilder"
ENTRY_NAME = "BuildDigitalTwin"
PYTHON_COMMAND = (
    "import importlib, digital_twin_builder; "
    "importlib.reload(digital_twin_builder); "
    "digital_twin_builder.run()"
)


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
