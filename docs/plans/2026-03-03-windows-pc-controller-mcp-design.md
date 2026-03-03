# Windows PC Controller MCP — Design Document

**Date:** 2026-03-03
**Status:** Approved
**Language:** Python

## Overview

An MCP (Model Context Protocol) server that gives Claude full control over a Windows PC — including screen vision, mouse/keyboard input, virtual gamepad emulation, ADB/BlueStacks control, and system management. Designed with **maximum security by default** and granular user configuration.

## Goals

- Claude can see and understand the screen (screenshots, OCR, pixel analysis)
- Claude can control input (mouse, keyboard, gamepad, ADB)
- Claude can manage apps and windows
- All capabilities are **secure by default** — locked down until the user explicitly enables them
- Security is configurable at a granular per-tool level
- Dangerous actions require **native Windows popup confirmation** with countdown timer

## Non-Goals

- No web-based UI (native popups only for confirmations)
- No audio capture/playback (out of scope)
- No network traffic manipulation

---

## Architecture

```
Claude (MCP Client)
        │ stdio / SSE
        ▼
┌─ MCP Server (Python) ──────────────────────────┐
│  Security Middleware Layer                       │
│  ├── Permission checker (per-tool policies)     │
│  ├── Region boundary enforcement                │
│  ├── Sensitive content masking                  │
│  ├── Audit logger                               │
│  ├── Rate limiter                               │
│  └── Confirmation popup (native Windows dialog) │
│                                                  │
│  Tool Handler Layer                              │
│  ├── Screen (capture, OCR, find, pixel, windows)│
│  ├── Mouse (move, click, drag, scroll, position)│
│  ├── Keyboard (type, hotkey, press)             │
│  ├── Gamepad (connect, input, disconnect)       │
│  ├── ADB (tap, swipe, key_event, shell)         │
│  ├── System (launch_app, focus/close window)    │
│  └── Clipboard (read, write)                    │
│                                                  │
│  Configuration (config.yaml + defaults)          │
└──────────────────────────────────────────────────┘
```

## Project Structure

```
windows-pc-controller-mcp/
├── src/
│   ├── server.py              # MCP server entry point
│   ├── config.py              # Config loader & validator
│   ├── security/
│   │   ├── middleware.py       # Central security gate (all tools pass through)
│   │   ├── masking.py         # Sensitive region/text masking
│   │   ├── audit.py           # Structured action audit logger
│   │   ├── rate_limiter.py    # Per-tool rate limiting
│   │   ├── permissions.py     # Permission policy engine
│   │   └── confirmation_popup.py  # Native Windows confirmation dialog
│   ├── tools/
│   │   ├── screen.py          # Screenshot, OCR, template match, pixel, windows
│   │   ├── mouse.py           # Mouse move, click, drag, scroll, position
│   │   ├── keyboard.py        # Type, hotkey, press
│   │   ├── gamepad.py         # Virtual Xbox 360 controller via ViGEmBus
│   │   ├── adb.py             # BlueStacks/Android emulator control
│   │   ├── system.py          # App launch, window focus/close, system info
│   │   └── clipboard.py       # Clipboard read/write
│   └── utils/
│       ├── win32_helpers.py    # Windows API wrappers
│       └── image_utils.py     # Image processing helpers
├── config/
│   ├── default.yaml           # Secure defaults (ships with MCP, not user-edited)
│   └── config.yaml            # User overrides (gitignored)
├── logs/                      # Audit logs (gitignored)
├── tests/
├── pyproject.toml
└── README.md
```

---

## Tools (26 total)

### Screen Capture & Vision (5 tools)

| Tool | Description | Default Security |
|------|-------------|-----------------|
| `capture_screenshot` | Screenshot of monitor/region/window, returns base64 | Masks sensitive regions, blocks password manager apps |
| `ocr_extract_text` | Extract text from screen region via EasyOCR | Redacts text from blocked apps |
| `find_on_screen` | Template matching — find where an image appears | Read-only, allowed |
| `get_pixel_color` | RGB color at coordinates | Read-only, allowed |
| `list_windows` | List visible windows with titles, positions, processes | Filters out blocklisted apps |

### Mouse Control (5 tools)

| Tool | Description | Default Security |
|------|-------------|-----------------|
| `mouse_move` | Move cursor to absolute/relative coordinates | Bounded to allowed regions |
| `mouse_click` | Click at coordinates (left/right/middle, single/double/triple) | Region check enforced |
| `mouse_drag` | Click and drag between two points | Region check enforced |
| `mouse_scroll` | Scroll by N clicks in any direction | Region bounded |
| `mouse_position` | Return current cursor position | Read-only, allowed |

### Keyboard Control (3 tools)

| Tool | Description | Default Security |
|------|-------------|-----------------|
| `keyboard_type` | Type a string with configurable speed | Blocks password fields, 500 char max |
| `keyboard_hotkey` | Press key combinations (e.g., Ctrl+C) | Dangerous combos blocked (Ctrl+Alt+Del, Win+L, Alt+F4) |
| `keyboard_press` | Press/release individual keys | Configurable blocked keys |

### Gamepad Emulation (3 tools)

| Tool | Description | Default Security |
|------|-------------|-----------------|
| `gamepad_connect` | Create virtual Xbox 360 controller | Requires ViGEmBus driver |
| `gamepad_input` | Set buttons, sticks, triggers | Only when session active |
| `gamepad_disconnect` | Disconnect virtual controller | Always allowed |

### ADB / BlueStacks (4 tools)

| Tool | Description | Default Security |
|------|-------------|-----------------|
| `adb_tap` | Tap at x,y on emulator | Configured device only |
| `adb_swipe` | Swipe between points | Configured device only |
| `adb_key_event` | Send Android key events | Configurable blocked events |
| `adb_shell` | Run shell command on emulator | **Allowlisted commands only** |

### System & App Management (4 tools)

| Tool | Description | Default Security |
|------|-------------|-----------------|
| `launch_app` | Open application by name/path | **Allowlist only** — empty by default |
| `focus_window` | Bring window to foreground | Allowed windows only |
| `close_window` | Close a window gracefully | Confirmation popup for system processes |
| `get_system_info` | CPU/RAM/disk/battery/display info | Sanitized — no usernames or paths |

### Clipboard (2 tools)

| Tool | Description | Default Security |
|------|-------------|-----------------|
| `clipboard_read` | Read clipboard contents | **Disabled by default** |
| `clipboard_write` | Write text to clipboard | Enabled, audit logged |

---

## Security Model

### Principle: Secure by Default

Every capability starts **locked down or maximally restricted**. Users explicitly opt in by editing `config/config.yaml`. The `config/default.yaml` ships with the MCP and defines the secure baseline.

### Security Middleware

All 26 tools pass through a centralized security middleware before execution:

1. **Tool enabled check** — is this tool turned on in config?
2. **Rate limit check** — has the per-tool rate limit been exceeded?
3. **Permission check** — allowlist/blocklist validation for the specific action
4. **Dangerous action detection** — does this action need user confirmation?
5. **Input sanitization** — validate and sanitize parameters
6. **Post-execution masking** — redact sensitive content from outputs
7. **Audit logging** — log every action with timestamp, tool, parameters, result

### Confirmation Popup

Dangerous actions trigger a **native Windows popup** (built with `customtkinter`):

- Shows: tool name, target, detailed description of what will happen
- Three buttons: **Allow**, **Deny**, **Deny with Reason** (opens text input)
- Live countdown timer displayed: `Auto-deny in 45s` (ticks every second)
- Auto-denies after timeout (default 60 seconds)
- Runs on a separate thread to avoid blocking the MCP event loop

Return values:
- **Allow** → tool executes normally
- **Deny** → returns `"User denied this action"`
- **Deny with Reason** → returns `"User denied this action: {reason}"`

### Default Security Configuration

```yaml
security:
  enabled: true
  confirm_dangerous_actions: true
  confirmation_timeout_seconds: 60
  audit_logging: true

  masking:
    enabled: true
    mask_password_fields: true
    blocked_apps:
      - "1Password"
      - "KeePass"
      - "LastPass"
      - "Bitwarden"
      - "Windows Security"
      - "Credential Manager"
    blocked_regions: []

  rate_limits:
    mouse: 60        # per minute
    keyboard: 120
    screenshot: 10
    adb: 30
    gamepad: 120

  keyboard:
    blocked_hotkeys:
      - "ctrl+alt+delete"
      - "win+l"
      - "alt+f4"
    max_type_length: 500
    block_password_fields: true

  apps:
    mode: "allowlist"
    allowed: []

  adb:
    allowed_devices: []
    allowed_commands:
      - "input tap"
      - "input swipe"
      - "input keyevent"
      - "screencap"
      - "dumpsys window"

  clipboard:
    read_enabled: false
    write_enabled: true
```

---

## Dependencies

| Library | Purpose |
|---------|---------|
| `mcp` | Official MCP Python SDK — protocol, tool registration, transport |
| `mss` | Fast multi-monitor screen capture |
| `easyocr` | OCR with good accuracy on game fonts and styled text |
| `Pillow` | Image processing and manipulation |
| `opencv-python` | Template matching and pixel-level analysis |
| `pynput` | Mouse and keyboard control/listening |
| `pywin32` | Direct Windows API access (SendInput, window management) |
| `vgamepad` | Virtual Xbox 360 / DS4 controller via ViGEmBus |
| `adb-shell` | Pure Python ADB client for emulator control |
| `pyyaml` | YAML config file parsing |
| `pydantic` | Config validation and type safety |
| `structlog` | Structured JSON audit logging |
| `customtkinter` | Modern-looking native confirmation popups |

---

## Error Handling

- **Structured errors**: Every tool returns `{ "success": false, "error": "message", "suggestion": "recovery hint" }`
- **No silent failures**: If masking fails, tool errors out rather than sending unmasked data
- **Timeouts**: Per-tool max execution time (5s screenshots, 10s OCR, etc.)
- **Recovery hints**: Errors include suggestions for Claude to try alternatives

---

## Data Flow

```
Claude sends tool call
  → Security Middleware validates
    → [If dangerous] Native popup with countdown
      → User allows/denies
    → Tool executes
      → Output masked/sanitized
        → Audit logged
          → Result returned to Claude
```
