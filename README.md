# Windows PC Controller MCP

An MCP (Model Context Protocol) server that gives Claude full control over your Windows PC — screen vision, mouse, keyboard, virtual gamepad, Android emulator, and system management. Built with maximum security by default.

**Python 3.11+** | **Windows 10/11** | **152 tests** | **MIT License**

---

## What Is This?

This is an [MCP server](https://modelcontextprotocol.io/) that connects to Claude Desktop (or any MCP client) and exposes **26 tools** across 7 categories. Once connected, Claude can:

- **See your screen** — take screenshots, read text via OCR, find UI elements, detect pixel colors
- **Control mouse & keyboard** — click, type, drag, scroll, press hotkeys
- **Play games with a gamepad** — emulate a virtual Xbox 360 controller with analog sticks and triggers
- **Control Android emulators** — tap, swipe, and send commands to BlueStacks or any ADB-connected device
- **Manage your system** — launch apps, switch windows, read clipboard, get system info

All of this is locked down by default. Every tool call passes through a security middleware with permission checks, rate limiting, audit logging, and native Windows confirmation popups for dangerous actions.

---

## Tools

### Screen Capture & Vision (5 tools)

| Tool                 | Description                                                                                |
| -------------------- | ------------------------------------------------------------------------------------------ |
| `capture_screenshot` | Take a screenshot of the full screen, a specific monitor, or a region. Returns base64 PNG. |
| `ocr_extract_text`   | Extract text from the screen or a region using EasyOCR.                                    |
| `find_on_screen`     | Find where a template image appears on screen using OpenCV template matching.              |
| `get_pixel_color`    | Get the RGB hex color of a pixel at screen coordinates.                                    |
| `list_windows`       | List all visible windows with titles, process names, and positions.                        |

### Mouse Control (5 tools)

| Tool             | Description                                                                                       |
| ---------------- | ------------------------------------------------------------------------------------------------- |
| `mouse_move`     | Move the cursor to absolute or relative coordinates.                                              |
| `mouse_click`    | Click at coordinates or current position. Supports left/right/middle, single/double/triple click. |
| `mouse_drag`     | Click and drag from start to end coordinates with configurable duration.                          |
| `mouse_scroll`   | Scroll the mouse wheel horizontally or vertically.                                                |
| `mouse_position` | Get the current cursor position.                                                                  |

### Keyboard Control (3 tools)

| Tool              | Description                                                                             |
| ----------------- | --------------------------------------------------------------------------------------- |
| `keyboard_type`   | Type a string of text character by character with configurable speed.                   |
| `keyboard_hotkey` | Press a key combination like `ctrl+c`, `alt+tab`, or `ctrl+shift+s`.                    |
| `keyboard_press`  | Press, release, or tap a single key (including special keys like F1-F12, arrows, etc.). |

### Virtual Gamepad (3 tools)

| Tool                 | Description                                                                                     |
| -------------------- | ----------------------------------------------------------------------------------------------- |
| `gamepad_connect`    | Create a virtual Xbox 360 controller (requires ViGEmBus driver).                                |
| `gamepad_input`      | Set buttons (A/B/X/Y/LB/RB/D-pad/etc.), analog sticks (-1.0 to 1.0), and triggers (0.0 to 1.0). |
| `gamepad_disconnect` | Disconnect the virtual controller.                                                              |

### Android Emulator / ADB (4 tools)

| Tool            | Description                                                     |
| --------------- | --------------------------------------------------------------- |
| `adb_tap`       | Tap at x,y on the emulator screen.                              |
| `adb_swipe`     | Swipe from one point to another with configurable duration.     |
| `adb_key_event` | Send an Android key event (e.g., 3=HOME, 4=BACK, 24=VOLUME_UP). |
| `adb_shell`     | Run an allowlisted ADB shell command on the emulator.           |

### System Management (4 tools)

| Tool              | Description                                                                  |
| ----------------- | ---------------------------------------------------------------------------- |
| `launch_app`      | Launch an application by name or path (must be in config allowlist).         |
| `focus_window`    | Bring a window to the foreground by title substring.                         |
| `close_window`    | Close a window gracefully by title (sends WM_CLOSE).                         |
| `get_system_info` | Get CPU, memory, disk, and battery info (sanitized — no usernames or paths). |

### Clipboard (2 tools)

| Tool              | Description                                                       |
| ----------------- | ----------------------------------------------------------------- |
| `clipboard_read`  | Read the current clipboard text content. **Disabled by default.** |
| `clipboard_write` | Write text to the clipboard.                                      |

---

## Prerequisites

| Requirement          | Notes                                                                                                                                                                                                                                    |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Windows 10 or 11** | Required — uses Win32 APIs for window management and input                                                                                                                                                                               |
| **Python 3.11+**     | Tested with Python 3.12                                                                                                                                                                                                                  |
| **ViGEmBus driver**  | _Optional_ — only needed for virtual gamepad. [Download here](https://github.com/nefarius/ViGEmBus/releases)                                                                                                                             |
| **ADB**              | _Optional_ — only needed for Android emulator control. Bundled with BlueStacks at `C:\Program Files\BlueStacks_nxt\HD-Adb.exe`, or install via [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools) |

---

## Installation

```bash
# Clone the repository
git clone https://github.com/Teja-sudo/windows-pc-controller-mcp.git
cd windows-pc-controller-mcp

# Install the package
pip install -e .

# Install dev dependencies (for running tests)
pip install -e ".[dev]"

# Verify everything works
python -m pytest tests/ -v
```

You should see all 152 tests passing.

---

## Integration

### Claude Desktop

Add this server to your Claude Desktop configuration file:

**Config file location:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "windows-pc-controller": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "C:\\path\\to\\windows-pc-controller-mcp"
    }
  }
}
```

Replace the `cwd` path with the actual location where you cloned this project. Restart Claude Desktop after editing the config.

### Claude Code (CLI)

One command to add the server globally (available in all Claude Code sessions):

```bash
claude mcp add --scope user windows-pc-controller -- python -m src.server --cwd "C:\path\to\windows-pc-controller-mcp"
```

Replace the path with the actual location where you cloned this project.

**Other scopes:**

```bash
# Project-level only (saved to .claude/settings.json in current project)
claude mcp add --scope project windows-pc-controller -- python -m src.server --cwd "C:\path\to\windows-pc-controller-mcp"
```

**Verify the connection:**

```bash
# List registered MCP servers
claude mcp list

# Check server details
claude mcp get windows-pc-controller
```

You should see `windows-pc-controller` with 26 tools available.

### Usage Examples

Once connected (via either Claude Desktop or Claude Code), you can ask Claude things like:

- _"Take a screenshot and tell me what's on screen"_
- _"Move the mouse to the Start button and click it"_
- _"Open Notepad and type 'Hello World'"_
- _"Connect a gamepad and press the A button"_
- _"Tap at 500,300 on my BlueStacks emulator"_
- _"What's the current CPU and memory usage?"_
- _"Find the 'Submit' button on screen and click it"_
- _"Read what's in my clipboard"_

---

## Configuration

### How It Works

The config system uses two YAML files with deep merging:

1. **`config/default.yaml`** — Ships with the project. Contains all secure defaults. **Never edit this file.**
2. **`config/config.yaml`** — Your personal overrides. **Gitignored.** Only add the settings you want to change.

Your `config.yaml` is merged on top of `default.yaml` — any value you specify overrides the default, everything else keeps its secure default. You only need to include the keys you want to change.

---

### Complete Configuration Reference

Below is every configurable option, organized by section. The YAML path shows exactly where each setting lives in your `config/config.yaml`.

#### Global Security Settings

```yaml
security:
  enabled: true # Master kill switch — disables ALL security checks
  confirm_dangerous_actions: true # Show native popup for dangerous tools
  confirmation_timeout_seconds: 60 # Auto-deny if no response (in seconds)
  audit_logging: true # Log every tool call to logs/audit.log
```

| Key                                     | Type   | Default | Description                                                                                                                            |
| --------------------------------------- | ------ | ------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `security.enabled`                      | `bool` | `true`  | Master switch for all security checks. When `false`, all tools are allowed without any permission, rate limit, or confirmation checks. |
| `security.confirm_dangerous_actions`    | `bool` | `true`  | Whether dangerous tools trigger a native Windows confirmation popup.                                                                   |
| `security.confirmation_timeout_seconds` | `int`  | `60`    | Seconds before the confirmation popup auto-denies. The countdown is shown live on the popup.                                           |
| `security.audit_logging`                | `bool` | `true`  | Whether all tool calls (allowed and denied) are logged to `logs/audit.log` in JSON-lines format.                                       |

#### Content Masking

Controls what sensitive content is hidden from Claude.

```yaml
security:
  masking:
    enabled: true # Toggle all masking on/off
    mask_password_fields: true # Redact password input fields
    blocked_apps: # Apps hidden from window listing & screenshots
      - "1Password"
      - "KeePass"
      - "LastPass"
      - "Bitwarden"
      - "Windows Security"
      - "Credential Manager"
    blocked_regions: [] # Screen regions to block [{left, top, width, height}]
```

| Key                                     | Type                               | Default             | Description                                                                                                                          |
| --------------------------------------- | ---------------------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `security.masking.enabled`              | `bool`                             | `true`              | Master toggle for all content masking.                                                                                               |
| `security.masking.mask_password_fields` | `bool`                             | `true`              | Whether to redact password input fields from OCR/screenshots.                                                                        |
| `security.masking.blocked_apps`         | `list[str]`                        | 6 password managers | App names (matched against window title and process name, case-insensitive) to hide from `list_windows` and filter from screenshots. |
| `security.masking.blocked_regions`      | `list[{left, top, width, height}]` | `[]`                | Specific screen rectangles to always mask. Useful for blocking a taskbar notification area, etc.                                     |

#### Rate Limits

Per-category limits on how many tool calls are allowed per minute. Uses a sliding window — once exceeded, further calls are blocked until older calls fall outside the window.

```yaml
security:
  rate_limits:
    mouse: 60 # mouse_move, mouse_click, mouse_drag, mouse_scroll, mouse_position
    keyboard: 120 # keyboard_type, keyboard_hotkey, keyboard_press
    screenshot: 10 # capture_screenshot, ocr_extract_text, find_on_screen, get_pixel_color, list_windows
    adb: 30 # adb_tap, adb_swipe, adb_key_event, adb_shell
    gamepad: 120 # gamepad_connect, gamepad_input, gamepad_disconnect
```

| Key                               | Type  | Default | Tools in category                                                                             |
| --------------------------------- | ----- | ------- | --------------------------------------------------------------------------------------------- |
| `security.rate_limits.mouse`      | `int` | `60`    | `mouse_move`, `mouse_click`, `mouse_drag`, `mouse_scroll`, `mouse_position`                   |
| `security.rate_limits.keyboard`   | `int` | `120`   | `keyboard_type`, `keyboard_hotkey`, `keyboard_press`                                          |
| `security.rate_limits.screenshot` | `int` | `10`    | `capture_screenshot`, `ocr_extract_text`, `find_on_screen`, `get_pixel_color`, `list_windows` |
| `security.rate_limits.adb`        | `int` | `30`    | `adb_tap`, `adb_swipe`, `adb_key_event`, `adb_shell`                                          |
| `security.rate_limits.gamepad`    | `int` | `120`   | `gamepad_connect`, `gamepad_input`, `gamepad_disconnect`                                      |

System tools (`launch_app`, `focus_window`, `close_window`, `get_system_info`) and clipboard tools (`clipboard_read`, `clipboard_write`) are not rate-limited by default.

#### Keyboard Security

```yaml
security:
  keyboard:
    blocked_hotkeys: # Hotkey combos that are always denied
      - "ctrl+alt+delete"
      - "win+l"
      - "alt+f4"
    max_type_length: 500 # Max characters per keyboard_type call
    block_password_fields: true # Prevent typing into password fields
```

| Key                                       | Type        | Default                                  | Description                                                                                                          |
| ----------------------------------------- | ----------- | ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `security.keyboard.blocked_hotkeys`       | `list[str]` | `["ctrl+alt+delete", "win+l", "alt+f4"]` | Hotkey combinations that are always denied, regardless of other permissions. Matched case-insensitively.             |
| `security.keyboard.max_type_length`       | `int`       | `500`                                    | Maximum number of characters allowed in a single `keyboard_type` call. Prevents Claude from pasting massive strings. |
| `security.keyboard.block_password_fields` | `bool`      | `true`                                   | Whether to prevent typing into detected password input fields.                                                       |

#### App Launch Control

```yaml
security:
  apps:
    mode: "allowlist" # "allowlist" or "blocklist"
    allowed: [] # Apps permitted to launch (empty = none)
```

| Key                     | Type                           | Default       | Description                                                                                                                                                 |
| ----------------------- | ------------------------------ | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `security.apps.mode`    | `"allowlist"` or `"blocklist"` | `"allowlist"` | In **allowlist** mode, only apps in `allowed` can be launched. In **blocklist** mode, all apps can be launched _except_ those listed. Allowlist is safer.   |
| `security.apps.allowed` | `list[str]`                    | `[]` (empty)  | App names or full paths. In allowlist mode, only these can be launched. In blocklist mode, these are blocked. **Empty allowlist = no app can be launched.** |

#### ADB (Android Emulator) Security

```yaml
security:
  adb:
    allowed_devices: [] # Restrict to specific ADB device serials
    allowed_commands: # Command prefixes that are permitted
      - "input tap"
      - "input swipe"
      - "input keyevent"
      - "screencap"
      - "dumpsys window"
```

| Key                             | Type        | Default           | Description                                                                                                                         |
| ------------------------------- | ----------- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `security.adb.allowed_devices`  | `list[str]` | `[]` (any device) | If non-empty, only these ADB device serials (e.g., `"emulator-5554"`) can be targeted. Empty means any connected device is allowed. |
| `security.adb.allowed_commands` | `list[str]` | 5 safe commands   | Command **prefixes** that are allowed for `adb_shell`. A command is allowed if it starts with any entry in this list.               |

#### Clipboard Security

```yaml
security:
  clipboard:
    read_enabled: false # Reading clipboard is OFF by default
    write_enabled: true # Writing to clipboard is allowed
```

| Key                                | Type   | Default | Description                                                                                                                                           |
| ---------------------------------- | ------ | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `security.clipboard.read_enabled`  | `bool` | `false` | Whether Claude can read your clipboard contents. **Disabled by default** to prevent accidental exposure of passwords or sensitive data you've copied. |
| `security.clipboard.write_enabled` | `bool` | `true`  | Whether Claude can write text to your clipboard.                                                                                                      |

#### Per-Tool Enable/Disable

Every tool can be individually enabled or disabled. This gives you granular control over exactly which capabilities Claude has access to.

```yaml
tools:
  # Screen tools
  capture_screenshot:
    enabled: true
  ocr_extract_text:
    enabled: true
  find_on_screen:
    enabled: true
  get_pixel_color:
    enabled: true
  list_windows:
    enabled: true

  # Mouse tools
  mouse_move:
    enabled: true
  mouse_click:
    enabled: true
  mouse_drag:
    enabled: true
  mouse_scroll:
    enabled: true
  mouse_position:
    enabled: true

  # Keyboard tools
  keyboard_type:
    enabled: true
  keyboard_hotkey:
    enabled: true
  keyboard_press:
    enabled: true

  # Gamepad tools
  gamepad_connect:
    enabled: true
  gamepad_input:
    enabled: true
  gamepad_disconnect:
    enabled: true

  # ADB tools
  adb_tap:
    enabled: true
  adb_swipe:
    enabled: true
  adb_key_event:
    enabled: true
  adb_shell:
    enabled: true

  # System tools
  launch_app:
    enabled: true
  focus_window:
    enabled: true
  close_window:
    enabled: true
  get_system_info:
    enabled: true

  # Clipboard tools
  clipboard_read:
    enabled: false # Disabled by default
  clipboard_write:
    enabled: true
```

Set any tool to `enabled: false` to completely block it. A disabled tool will return an error immediately without executing.

---

### Example Configurations

#### Gaming Setup (Relaxed Limits)

```yaml
security:
  rate_limits:
    mouse: 240
    keyboard: 240
    gamepad: 240
  keyboard:
    max_type_length: 1000
```

#### BlueStacks Automation

```yaml
security:
  adb:
    allowed_devices:
      - "emulator-5554"
    allowed_commands:
      - "input tap"
      - "input swipe"
      - "input keyevent"
      - "input text"
      - "screencap"
      - "getprop"
      - "dumpsys window"
      - "dumpsys activity"
```

#### Read-Only Observer (No Input)

```yaml
tools:
  mouse_move:
    enabled: false
  mouse_click:
    enabled: false
  mouse_drag:
    enabled: false
  mouse_scroll:
    enabled: false
  keyboard_type:
    enabled: false
  keyboard_hotkey:
    enabled: false
  keyboard_press:
    enabled: false
  gamepad_connect:
    enabled: false
  gamepad_input:
    enabled: false
  gamepad_disconnect:
    enabled: false
  adb_tap:
    enabled: false
  adb_swipe:
    enabled: false
  adb_key_event:
    enabled: false
  adb_shell:
    enabled: false
  launch_app:
    enabled: false
  close_window:
    enabled: false
  clipboard_write:
    enabled: false
```

#### Allow Specific Apps

```yaml
security:
  apps:
    mode: "allowlist"
    allowed:
      - "notepad.exe"
      - "calc.exe"
      - "mspaint.exe"
      - "C:\\Program Files\\BlueStacks_nxt\\HD-Player.exe"
  clipboard:
    read_enabled: true
```

---

## Security Model

### Philosophy: Secure by Default

Every capability starts **locked down**. You explicitly opt in by editing `config/config.yaml`. There is no "trust all" mode — even with security disabled, the structural safeguards remain.

### Security Layers

Every tool call passes through these layers in order:

```
Claude sends tool call
        |
        v
[1. Permission Check]     Is this tool enabled? Is this command/app allowlisted?
        |
        v
[2. Rate Limit Check]     Has this category exceeded its per-minute limit?
        |
        v
[3. Confirmation Popup]   Is this a dangerous action? Show native Windows popup.
        |
        v
[4. Tool Execution]       Run the actual tool function.
        |
        v
[5. Audit Log]            Log the call, parameters, and result to logs/audit.log
```

### Dangerous Action Confirmation

Four tools are flagged as **dangerous** and trigger a native Windows popup before execution:

- `close_window` — Could close unsaved work
- `launch_app` — Could run arbitrary executables
- `adb_shell` — Could execute commands on connected devices
- `keyboard_hotkey` — Could trigger system-level shortcuts

When triggered, a popup appears with:

- The tool name and all parameters being passed
- **Allow** button (green) — proceed with the action
- **Deny** button (red) — block the action
- **Deny with Reason** button — block and send a reason back to Claude
- **Live countdown timer** — auto-denies after timeout (default: 60 seconds)

The popup is a native Windows dialog (CustomTkinter with dark theme) — it does **not** rely on Claude to relay the confirmation. You always have the final say.

### Content Masking

- **Password manager windows** are automatically filtered from `list_windows` results and can be excluded from screenshots
- **System info** is sanitized — no usernames, file paths, or hostname exposed
- Configurable `blocked_apps` list in `config/default.yaml`

### Audit Logging

Every tool call is logged to `logs/audit.log` in JSON-lines format:

```json
{
  "timestamp": "2026-03-03T14:30:00",
  "tool": "mouse_click",
  "params": { "x": 500, "y": 300 },
  "allowed": true,
  "result_summary": "{\"success\": true, \"button\": \"left\"}"
}
```

Denied actions are also logged with the denial reason.

---

## Architecture

```
windows-pc-controller-mcp/
├── src/
│   ├── server.py              # MCP entry point — registers 26 tools, dispatches calls
│   ├── config.py              # YAML config loader with Pydantic validation
│   ├── security/
│   │   ├── middleware.py      # Central security gate (pre_check + post_log)
│   │   ├── permissions.py     # Permission checker (allowlist/blocklist, tool enable/disable)
│   │   ├── rate_limiter.py    # Sliding-window rate limiter per category
│   │   ├── audit.py           # JSON-lines audit logger
│   │   ├── confirmation_popup.py  # Native Windows popup with countdown
│   │   └── masking.py         # Sensitive window/content filtering
│   ├── tools/
│   │   ├── screen.py          # Screenshot, OCR, template matching, pixel color
│   │   ├── mouse.py           # Mouse move, click, drag, scroll
│   │   ├── keyboard.py        # Type, hotkey, press
│   │   ├── gamepad.py         # Virtual Xbox 360 via ViGEmBus
│   │   ├── adb.py             # Android emulator control via ADB
│   │   ├── system.py          # App launch, window focus/close, system info
│   │   └── clipboard.py       # Clipboard read/write
│   └── utils/
│       ├── win32_helpers.py   # Windows API wrappers for window management
│       └── image_utils.py     # PIL/OpenCV image conversion, template matching
├── tests/                     # 152 tests — one test file per module
├── config/
│   └── default.yaml           # Secure defaults (never edit)
├── logs/                      # Audit logs (gitignored)
└── pyproject.toml             # Dependencies and entry point
```

### Data Flow

```
MCP Client (Claude Desktop)
    |
    | stdio (JSON-RPC)
    v
src/server.py
    |
    |-- list_tools()  -->  Returns 26 tool definitions
    |
    |-- call_tool(name, args)
            |
            v
        SecurityMiddleware.pre_check()
            |-- PermissionChecker: tool enabled? command allowed?
            |-- RateLimiter: within limits?
            |-- (if dangerous) ConfirmationPopup: user approves?
            |
            v
        _dispatch_tool() --> routes to correct handler
            |
            v
        Tool executes (mouse.py, keyboard.py, etc.)
            |
            v
        SecurityMiddleware.post_log()
            |
            v
        Return TextContent (JSON) or ImageContent (screenshot)
```

### Key Dependencies

| Library         | Purpose                                         |
| --------------- | ----------------------------------------------- |
| `mcp`           | MCP protocol server framework                   |
| `mss`           | Fast multi-monitor screen capture               |
| `easyocr`       | OCR text extraction                             |
| `opencv-python` | Template matching for find-on-screen            |
| `Pillow`        | Image processing and conversion                 |
| `pynput`        | Mouse and keyboard control                      |
| `pywin32`       | Windows API (window management, clipboard)      |
| `vgamepad`      | Virtual Xbox 360 controller emulation           |
| `pyyaml`        | YAML configuration parsing                      |
| `pydantic`      | Configuration validation with type safety       |
| `customtkinter` | Modern UI for confirmation popups               |
| `psutil`        | System information (CPU, memory, disk, battery) |

---

## Development

### Running Tests

```bash
# Run all 152 tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_server.py -v

# Run tests matching a pattern
python -m pytest tests/ -k "gamepad" -v
```

All tests use `unittest.mock` to mock hardware dependencies — no real mouse movements, keyboard presses, or screenshots happen during testing.

### Adding a New Tool

1. **Create the tool function** in the appropriate `src/tools/*.py` file (or a new one)
2. **Add tests** in `tests/test_*.py`
3. **Add the tool definition** to `TOOL_DEFINITIONS` in `src/server.py`
4. **Add the dispatcher entry** in `_dispatch_tool()` in `src/server.py`
5. **Add the tool config** to `config/default.yaml` under `tools:`
6. **Map the rate limit category** in `TOOL_CATEGORY` in `src/security/middleware.py`

### Project Scripts

```bash
# Start the MCP server (connects via stdio)
python -m src.server

# Or use the installed entry point
windows-pc-controller-mcp
```

---

## License

MIT License - Copyright (c) 2026 Sanikommu Teja

See [LICENSE](LICENSE) for details.
