# wlaunch

A Raycast-like launcher for Linux, optimized for i3wm.

## Features

*   **Application Launcher**: Quickly find and launch applications.
*   **Window Switcher**: Navigate between open windows (requires i3wm).
*   **Clipboard Manager**: History of copied text.
*   **AI Assistant**: Integration with Google Gemini for quick queries.
*   **Bitwarden Integration**: Access your passwords directly.
*   **Calculator & Converter**: Quick math and unit conversions.
*   **File Search**: Find recent files.

## Prerequisites

*   Python 3.10 or higher
*   `git`
*   A Google Gemini API key (for AI features)

## Installation

This project is intended to be installed directly via `git clone`.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/wlaunch.git
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
