# wlaunch

A Raycast-like launcher for Linux, optimized for i3wm.

## Features

*   **Application Launcher**: Quickly find and launch applications.
*   **Window Switcher**: Navigate between open windows (requires i3wm).
*   **Clipboard Manager**: History of copied text.
*   **Network Manager**: Manage WiFi connections (toggle, connect, scan).
*   **AI Assistant**: Integration with Google Gemini for quick queries.
*   **Bitwarden Integration**: Access your passwords, cards, and secure notes directly.
*   **Calculator & Converter**: Quick math and unit conversions.
*   **File Search**: Find recent files.
*   **Process Manager**: Kill unresponsive processes.

## Prerequisites

### System Dependencies
Ensure these system packages are installed:
*   `python` (3.10+)
*   `git`
*   `nmcli` (NetworkManager CLI - for WiFi management)
*   `libxcb` (Standard Qt dependency on Linux)
*   `i3` (For window switching features, optional but recommended)

### Python Dependencies
Installed automatically via `requirements.txt`:
*   `PyQt6` (GUI Framework)
*   `pyxdg` (Desktop entry parsing)
*   `google-generativeai` (AI features)
*   `requests`
*   `cryptography`
*   `i3ipc` (i3 window management)

## Installation

This project is intended to be installed directly via `git clone`.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/kpanuragh/wlaunch.git
    cd wlaunch
    ```

2.  **Set up a virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

### Gemini API Key
To use the AI features, you need to configure your Gemini API key.

1.  Create the configuration directory:
    ```bash
    mkdir -p ~/.config/wlaunch
    ```

2.  Create a `config.json` file in `~/.config/wlaunch/`:
    ```json
    {
        "gemini_api_key": "YOUR_API_KEY_HERE"
    }
    ```

## Usage

### Launcher
To start the launcher, run the `wlaunch.sh` script. You typically want to bind this to a keyboard shortcut in your window manager config (e.g., in i3 config).

```bash
/path/to/wlaunch/wlaunch.sh
```

**Example i3 config:**
```i3
bindsym $mod+d exec --no-startup-id /home/youruser/Projects/wlaunch/wlaunch.sh
```

### Daemon (Clipboard Manager)
For features like the clipboard manager to work, the daemon needs to be running in the background.

Add this to your startup script (e.g., i3 config):

```bash
exec --no-startup-id /path/to/wlaunch/wlaunch-daemon.sh
```

## Keybindings & Commands

| Mode / Command | Action | Example |
| :--- | :--- | :--- |
| **General** | | |
| `Esc` | Close launcher | |
| `Enter` | Execute / Open / Copy | |
| `Up` / `Down` | Navigate list | |
| **System** | | |
| `wifi` | **Manage Network**: Toggle On/Off, Scan, Connect | `wifi` |
| `w <query>` | **Window Switcher**: Search open windows | `w firefox` |
| `ps <query>` | **Process Manager**: Search and kill processes | `ps chrome` |
| `shutdown` | Shutdown system | |
| `reboot` | Reboot system | |
| `suspend` | Suspend system | |
| **Productivity** | | |
| `cb <query>` | **Clipboard History**: Search past copies | `cb url` |
| `r <query>` | **Recent Files**: Search recently used files | `r report` |
| `f <query>` | **File Search**: Search files by name | `f photo.jpg` |
| `ask <query>` | **AI Assistant**: Ask Google Gemini | `ask python list sort` |
| **Bitwarden** | | |
| `bw` | **Login/Unlock**: Access vault | `bw` |
| `bw <query>` | Search Logins (Copy Password/Username) | `bw google` |
| `bw gen` | Generate secure password | |
| `bw totp <query>`| Get TOTP code | `bw totp github` |
| `bw card <query>`| Search Credit Cards | `bw card visa` |
| `bw note <query>`| Search Secure Notes | `bw note secret` |
| **Web** | | |
| `g <query>` | Google Search | `g linux news` |
| `gh <query>` | GitHub Search | `gh wlaunch` |
| `yt <query>` | YouTube Search | `yt tutorials` |
| **Utilities** | | |
| `e <query>` | **Emoji Picker**: Copy emoji to clipboard | `e smile` |
| `<math>` | **Calculator**: Evaluate expression | `128 * 4` |
| `<unit>` | **Converter**: Convert units (e.g. currency) | `100 usd in eur` |