# wlaunch

A modern, extensible, Raycast-inspired application launcher for Linux (specifically i3/tiling WMs), built with Python and PyQt6.

![wlaunch](https://via.placeholder.com/800x450?text=wlaunch+Screenshot)

## Features

*   **🚀 Application Launcher:** Blazing fast fuzzy search for all your installed applications.
*   **📋 Clipboard Manager:** Built-in history manager. Type `cb` to search and paste recent copies.
*   **🧮 Calculator:** Inline math evaluation (e.g., `50 * 5` or `(12+4)/2`).
*   **🌐 Web Search:** Quick aliases for common services:
    *   `g query...` - Google Search
    *   `gh query...` - GitHub Search
    *   `yt query...` - YouTube Search
*   **📜 Script Extensions:** Drop any script into `~/.config/wlaunch/scripts/` and it becomes a searchable command.
*   **🧠 AI Assistant:** Type `ask your question...` to get answers from Google's Gemini AI.
*   **🖥️ System Commands:** Built-in support for Shutdown, Reboot, Log Out, and i3 Reload.
*   **🎨 Modern UI:** Frameless, dark-themed, window-centered design with a split-pane details view.

## Installation

### DEB (Debian/Ubuntu/Pop!_OS)
Download the latest `.deb` from Releases.
```bash
sudo apt install ./wlaunch.deb
systemctl --user enable --now wlaunch-daemon  # Enable clipboard history
```

### RPM (Fedora/RedHat)
Download the latest `.rpm` from Releases.
```bash
sudo rpm -i wlaunch.rpm
systemctl --user enable --now wlaunch-daemon
```

### Manual
1.  Clone the repo:
    ```bash
    git clone https://github.com/kpanuragh/wlaunch.git
    cd wlaunch
    ```
2.  Install dependencies:
    ```bash
    pip install PyQt6 pyxdg
    ```
3.  Run:
    ```bash
    ./wlaunch.py
    ```

## Usage

### Keybindings (i3)
Add this to your `~/.config/i3/config`:
```i3
bindsym $mod+d exec --no-startup-id wlaunch
```

### Clipboard Daemon
To ensure your clipboard history is tracked even when the launcher is closed, ensure the background service is running:
```bash
wlaunch-daemon &
```
(The package installs a systemd user service for this automatically).

## Configuration
*   **AI Assistant Configuration:** To use the AI Assistant feature, you need a Google Gemini API key.
    1.  Obtain an API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
    2.  Create a configuration file at `~/.config/wlaunch/config.json` with the following content, replacing `"YOUR_ACTUAL_API_KEY_HERE"` with your obtained key:
        ```json
        {
            "gemini_api_key": "YOUR_ACTUAL_API_KEY_HERE"
        }
        ```
*   **Styles:** Edit `/usr/share/wlaunch/styles.qss` (or local `styles.qss`) to customize the look.
*   **Scripts:** Put executable files in `~/.config/wlaunch/scripts/`.

## License
MIT
