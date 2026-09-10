# Digital Twin Builder

Unreal Engine **5.6+** editor plugin that builds a **digital twin** of a room from photos or a video and spawns it in the level.

This folder is **standalone**. Zip and share `DigitalTwinBuilder` only. You do **not** need any of these from another project:

- `Content/python/EditorTools/DigitalTwinBuilder`
- `Content/python/DigitalTwinBuilder`
- `Content/python/AutomatedSyntheticDataPipeline` / ObjectLocator

---

## What it does

1. You pick **multiple images** (Ctrl+click) or **one video**.
2. The plugin runs **YOLO-World** on **system Python 3.12** (not Unreal’s embedded Python).
3. Detected objects (desk, chairs, laptop, monitor, etc.) are laid out as furniture parts.
4. Colored unlit meshes are spawned into `/Game/DigitalTwin/Maps/Lvl_DigitalTwin`.
5. Live progress streams to the **Output Log**.

Unreal Python only handles the file picker, progress, and spawning. Detection always uses `py -3.12`.

---

## Requirements

| Requirement | Notes |
|---|---|
| Unreal Engine **5.6+** | Editor only (not packaged runtime) |
| **Python Editor Script Plugin** | Built-in Unreal plugin |
| **Editor Scripting Utilities** | Built-in Unreal plugin |
| **Python 3.12** on Windows | `py -3.12` launcher |
| pip packages | `ultralytics`, `opencv-python`, `numpy` |

---

## Install the plugin

### Option 1 — Clone from GitHub (includes models)

YOLO and CLIP weights are stored with **Git LFS**. Install [Git LFS](https://git-lfs.com), then:

```bat
git lfs install
git clone https://github.com/M-Usamah/DigitalTwinBuilder.git
```

Copy the cloned `DigitalTwinBuilder` folder into your Unreal project’s `Plugins` directory.

If a clone is missing `.pt` files, run `git lfs pull` inside the repo.

### Option 2 — Copy the folder

1. Copy the entire **`DigitalTwinBuilder`** folder into your project’s `Plugins` directory.

   The path must look like this:

   ```
   YourProject/
   ├── Content/
   ├── Plugins/
   │   └── DigitalTwinBuilder/          ← this folder
   │       ├── DigitalTwinBuilder.uplugin
   │       ├── README.md
   │       └── Content/Python/
   └── YourProject.uproject
   ```

   Example:

   `C:\Users\YourName\Documents\Unreal Projects\MyGame\Plugins\DigitalTwinBuilder`

2. Keep the folder name **`DigitalTwinBuilder`**. Do **not** put it under `Content/`.

3. Install the Python packages used by the pipeline (once per machine):

   ```bat
   py -3.12 -m pip install -r "Plugins\DigitalTwinBuilder\Content\Python\Pipeline\requirements.txt"
   ```

   Weights ship with the plugin (`yolov8s-world.pt` and CLIP `ViT-B-32.pt`). If they are missing, the first run may download them (internet required).

---

## Enable the plugin in Unreal Engine

### A) Enable required engine plugins

1. Open the project in Unreal Editor.
2. **Edit → Plugins**.
3. Search and **enable**:
   - **Python Editor Script Plugin** (listed as **Python**)
   - **Editor Scripting Utilities**
4. Restart the editor if Unreal asks you to.

### B) Enable Digital Twin Builder

1. **Edit → Plugins**.
2. Search **Digital Twin Builder**.
3. Check **Enabled**.
4. **Restart Unreal Editor** (required the first time).

### C) Optional — always enable from the `.uproject` file

Open `YourProject.uproject` in a text editor. Inside the `"Plugins"` array, add:

```json
{
  "Name": "DigitalTwinBuilder",
  "Enabled": true
}
```

Save the file, then reopen the project.

### D) If the Tools menu item is missing

1. **Edit → Project Settings → Plugins → Python**.
2. Under **Additional Paths**, add:

   ```
   Plugins/DigitalTwinBuilder/Content/Python
   ```

3. Fully quit Unreal and open the project again (not just reload the level).

On a successful start, Output Log should contain:

`Digital Twin Builder: Tools menu registered.`

---

## How to use

1. Restart Unreal after install/enable.
2. **Tools → Digital Twin Builder → Build Digital Twin from Images/Video...**
3. Select images (Ctrl+click) or one video, then Open.
4. Watch **Window → Output Log** for progress.
5. When finished, open **Content Browser → DigitalTwin → Maps → Lvl_DigitalTwin**.

### Run from the Python console (optional)

In Output Log, switch to Python and run:

```python
import importlib, digital_twin_builder
importlib.reload(digital_twin_builder)
digital_twin_builder.run()
```

---

## Project layout (this plugin)

```
DigitalTwinBuilder/
├── DigitalTwinBuilder.uplugin
├── README.md
├── INSTALL_INSTRUCTIONS.txt
└── Content/Python/
    ├── init_unreal.py              # Registers the Tools menu
    ├── digital_twin_builder.py     # Editor entry (picker → pipeline → spawn)
    ├── dt_picker.py
    ├── dt_progress.py
    ├── dt_paths.py
    ├── dt_spawn.py
    ├── dt_materials.py
    └── Pipeline/                   # System Python 3.12 (YOLO + layout)
        ├── export_unreal_scene.py
        ├── dt_detect.py
        ├── dt_furniture.py
        └── requirements.txt
```

---

## Troubleshooting

| Problem | What to do |
|---|---|
| Menu missing | Restart editor. Enable this plugin + Python plugins. Add Additional Paths (step D). |
| `ultralytics` / preprocess failed | Run `py -3.12 -c "import ultralytics; print('ok')"` then install `requirements.txt`. |
| `export_unreal_scene.py not found` | The `Content/Python/Pipeline` folder is missing — copy the full plugin. |
| Twin in a black / empty sky | Open `Content/DigitalTwin/Maps/Lvl_DigitalTwin`. The viewport should frame the twin. |
| Running scripts outside Unreal | `digital_twin_builder.py` is Editor-only. `Pipeline/export_unreal_scene.py` can be tested with `py -3.12`. |

---

## Sharing

Zip **only** the `DigitalTwinBuilder` folder. Do not include `Binaries/` or `Intermediate/` if they appear later.

To update: replace the plugin folder and restart Unreal.
