"""MilkyDawn Preset Dev — MCP Server for creating EYESY visual presets with LLMs"""

import asyncio
import json
import os
import shutil
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# MilkyDawn のインストールディレクトリ（環境変数で設定可能）
MILKYDAWN_DIR = Path(os.environ.get("MILKYDAWN_DIR", os.path.join(os.path.dirname(__file__), "..", "MilkyDawn")))
PRESETS_DIR = MILKYDAWN_DIR / "presets"
CMD_FILE = MILKYDAWN_DIR / "mcp_cmd.json"

app = Server("milkydawn-presets")

# ── API リファレンス ──

API_REFERENCE = """\
# EYESY Preset API Reference

## File Structure
Create presets/<NAME>/main.py with setup() and draw() functions.
The folder name becomes the preset name.

## Required Functions

```python
import pygame
import math

def setup(screen, etc):
    # Called once when the mode is activated. Initialize global state here.
    global phase
    phase = 0.0

def draw(screen, etc):
    # Called every frame (~60fps). Draw visuals here.
    etc.color_picker_bg(etc.knob5)  # MUST call at start to clear screen
    color = etc.color_picker(etc.knob1)
    # Use pygame.draw.* to render on the screen surface
```

## etc Object Attributes

### Screen Size
- etc.xres — int, screen width
- etc.yres — int, screen height

### Knob Parameters (all float 0.0-1.0, controlled by UI sliders)
- etc.knob1 — Color: use etc.color_picker(etc.knob1) to get foreground (R,G,B)
- etc.knob2 — Size: use as scale/shape parameter
- etc.knob3 — Trail: persistence/afterimage amount
- etc.knob4 — Amp: audio sensitivity multiplier
- etc.knob5 — Background: use etc.color_picker_bg(etc.knob5) for BG color & screen clear

### Audio Data (updated every frame)
- etc.audio_normalized — list[float], 100 samples, -1.0 to 1.0 (mono waveform)
- etc.audio_left       — list[float], 100 samples (left channel)
- etc.audio_right      — list[float], 100 samples (right channel)
- etc.fft              — list[float], 100 bins, 0 to 1 (FFT spectrum, low to high freq)
- etc.rms              — float (RMS volume level, typically 0 to ~0.3)
- etc.trig             — bool (beat/onset detection, True for one frame only)

### Methods
- etc.color_picker(v)     — float(0-1) -> (R,G,B) tuple from foreground palette
- etc.color_picker_bg(v)  — float(0-1) -> sets BG color and fills entire screen
- etc.color_picker_lfo(v) — time-animated color picker
- etc.mode_root           — str, absolute path to this preset's folder (for loading images)
- etc.bg_color            — (R,G,B), last background color set

## Important Rules
1. MUST call etc.color_picker_bg(etc.knob5) at the start of draw() to clear screen
2. Use etc.xres / etc.yres for coordinates, never hardcode screen size
3. Use module-level globals for state across frames; initialize in setup()
4. Only pygame, math, random, os are available (no pip packages)
5. Draw using pygame.draw.line/circle/rect/polygon/ellipse on the screen surface
6. Colors are (R, G, B) tuples with values 0-255

## Common Patterns

### Draw waveform as connected lines
```python
for i in range(len(etc.audio_normalized) - 1):
    x1 = int(i * etc.xres / 100)
    x2 = int((i + 1) * etc.xres / 100)
    y1 = int(etc.yres / 2 + etc.audio_normalized[i] * etc.yres * etc.knob4 * 0.4)
    y2 = int(etc.yres / 2 + etc.audio_normalized[i + 1] * etc.yres * etc.knob4 * 0.4)
    pygame.draw.line(screen, color, (x1, y1), (x2, y2), 2)
```

### Draw FFT as vertical bars
```python
bar_w = etc.xres // 100
for i in range(100):
    h = int(etc.fft[i] * etc.yres * etc.knob4)
    x = i * bar_w
    pygame.draw.rect(screen, color, (x, etc.yres - h, bar_w - 1, h))
```

### Trigger something on beat
```python
if etc.trig:
    # Do something on beat detection (spawn particle, change color, etc.)
    pass
```

### Load an image from preset folder
```python
def setup(screen, etc):
    global img
    img = pygame.image.load(os.path.join(etc.mode_root, 'images', 'my_image.png')).convert_alpha()
```
"""


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_presets",
            description="List all preset names in the presets/ directory",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="read_preset",
            description="Read the main.py source code of a preset",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Preset folder name"}},
                "required": ["name"],
            },
        ),
        types.Tool(
            name="write_preset",
            description="Create or overwrite a preset's main.py. Creates the folder if needed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Preset folder name"},
                    "code": {"type": "string", "description": "Python source code for main.py"},
                },
                "required": ["name", "code"],
            },
        ),
        types.Tool(
            name="delete_preset",
            description="Delete a preset folder and all its contents",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Preset folder name"}},
                "required": ["name"],
            },
        ),
        types.Tool(
            name="reload_visualizer",
            description="Signal the running MilkyDawn visualizer to reload all presets",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="select_preset",
            description="Signal the running MilkyDawn visualizer to switch to the specified preset",
            inputSchema={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Preset name to activate"}},
                "required": ["name"],
            },
        ),
        types.Tool(
            name="get_api_reference",
            description="Get the full EYESY preset API reference (etc object attributes, methods, and code patterns)",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "list_presets":
        if not PRESETS_DIR.exists():
            return [types.TextContent(type="text", text=f"presets/ directory not found at {PRESETS_DIR}")]
        names = sorted(d.name for d in PRESETS_DIR.iterdir() if d.is_dir())
        return [types.TextContent(type="text", text=json.dumps(names, ensure_ascii=False))]

    elif name == "read_preset":
        path = PRESETS_DIR / arguments["name"] / "main.py"
        if not path.exists():
            return [types.TextContent(type="text", text=f"Not found: {path}")]
        text = path.read_text(encoding="utf-8")
        return [types.TextContent(type="text", text=text)]

    elif name == "write_preset":
        dest = PRESETS_DIR / arguments["name"]
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "main.py").write_text(arguments["code"], encoding="utf-8")
        return [types.TextContent(type="text", text=f"Written: {dest / 'main.py'}")]

    elif name == "delete_preset":
        dest = PRESETS_DIR / arguments["name"]
        if dest.exists():
            shutil.rmtree(dest)
            return [types.TextContent(type="text", text=f"Deleted: {dest}")]
        return [types.TextContent(type="text", text=f"Not found: {dest}")]

    elif name == "reload_visualizer":
        CMD_FILE.write_text(json.dumps({"cmd": "reload"}), encoding="utf-8")
        return [types.TextContent(type="text", text="Reload command sent to visualizer")]

    elif name == "select_preset":
        CMD_FILE.write_text(
            json.dumps({"cmd": "select", "name": arguments["name"]}),
            encoding="utf-8",
        )
        return [types.TextContent(type="text", text=f"Select command sent: {arguments['name']}")]

    elif name == "get_api_reference":
        return [types.TextContent(type="text", text=API_REFERENCE)]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
