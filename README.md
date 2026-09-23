# Antigravity Quota Monitor

[![GNOME Shell](https://img.shields.io/badge/GNOME%20Shell-46-blue.svg)](https://extensions.gnome.org)
[![Platform](https://img.shields.io/badge/Platform-Ubuntu%2024.04%20LTS-orange.svg)](https://ubuntu.com)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL%203.0-green.svg)](LICENSE)

A lightweight, glanceable **GNOME Shell 46** extension that monitors your **Google Antigravity AI quota** across multiple active accounts directly inside the native calendar and notification tray menu.

---

## ✨ Features

- **Multi-Account Support:** Automatically detects and displays quota cards for each active Google account configured in your environment.
- **Glanceable Limit Tiers:**
  - ⚡ **Gemini (5h):** Rolling 5-hour quota percentage & countdown until reset.
  - 📅 **Gemini (7d):** Weekly quota percentage & countdown until reset.
  - 🤖 **Claude & GPT:** Weekly shared tier quota status (`ok` vs `exhausted`) & reset timer.
- **Native Look & Feel:** Seamlessly embeds below *World Clocks* in the top panel calendar tray, styled with clean cards and progress bars matching Adwaita / modern GNOME themes.
- **High-Contrast Adaptive Palette:**
  - 🟢 **Safe (> 20%):** Vibrant green indicator.
  - 🟡 **Warning (≤ 20%):** Warm amber indicator.
  - 🔴 **Exhausted (0%):** Crimson red indicator.
- **Non-Blocking & Battery Friendly:**
  - Instant event-driven fetch every time the calendar menu opens.
  - Periodic 60-second countdown updates only while the tray is actively open.
  - **Zero CPU usage** when the menu is closed.
  - Uses read-only SQLite WAL access (`file:.../agent.db?mode=ro`) without any database locking.

---

## 🚀 Installation

### Prerequisites
- GNOME Shell **46** (Ubuntu 24.04 LTS or compatible distribution)
- Python 3 (`python3`) installed
- Local Antigravity / OMP usage database (`~/.omp/agent/agent.db`)

### Quick Install (Automated Script)
Clone the repository and run the installation script:

```bash
git clone https://github.com/NaufalYogaPratama/antigravity-quota-monitor.git
cd antigravity-quota-monitor
./install.sh
```

### Manual Installation
1. Copy the extension directory to your GNOME extensions folder:
   ```bash
   mkdir -p ~/.local/share/gnome-shell/extensions
   cp -r . ~/.local/share/gnome-shell/extensions/antigravity-quota-monitor@naufal.dev
   ```

2. Register and enable the extension:
   ```bash
   gnome-extensions enable antigravity-quota-monitor@naufal.dev
   ```

3. **On Wayland:** If you are installing the extension for the first time, log out and log back in (or restart your session) for GNOME Shell to index the newly registered extension.

---

## 🛠️ Architecture

```
GNOME Shell Top Bar (dateMenu)
   │
   ├── [Open Event / 60s Interval]
   │
   ▼
extension.js (ESM Class)
   │
   ├── Gio.Subprocess (Non-blocking async pipe)
   │
   ▼
data_fetcher.py
   │
   ├── Read-Only SQLite URI Query (Zero lock)
   │
   ▼
~/.omp/agent/agent.db (usage_history & auth_credentials)
```

1. **`extension.js`**: Standard GNOME 46 ESM extension module that constructs the `St` UI components and connects to `dateMenu.menu` events.
2. **`data_fetcher.py`**: A minimal, self-contained Python script executing a read-only query on SQLite WAL tables and returning formatted JSON in `< 20ms`.
3. **`stylesheet.css`**: Provides styling for container cards, progress tracks, and color indicators.

---

## 🧪 Testing

Run the included unit test suite:

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Verify extension syntax:

```bash
node --input-type=module --check < extension.js
```

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE](LICENSE) file for details.
