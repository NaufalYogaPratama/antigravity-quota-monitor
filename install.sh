#!/bin/bash
set -e

EXT_UUID="antigravity-quota-monitor@naufal.dev"
TARGET_DIR="$HOME/.local/share/gnome-shell/extensions/$EXT_UUID"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installing $EXT_UUID ==="
mkdir -p "$HOME/.local/share/gnome-shell/extensions"
rm -rf "$TARGET_DIR"
cp -r "$SRC_DIR" "$TARGET_DIR"

# Clean up development/test artifacts from installed directory
rm -rf "$TARGET_DIR/.git" "$TARGET_DIR/.superpowers" "$TARGET_DIR/tests" "$TARGET_DIR/__pycache__"

echo "Verifying data fetcher in target directory..."
python3 "$TARGET_DIR/data_fetcher.py" > /dev/null
echo "✓ Data fetcher verified successfully."

echo "Registering $EXT_UUID into GNOME Shell enabled-extensions..."
python3 -c "
import subprocess, ast
out = subprocess.check_output(['gsettings', 'get', 'org.gnome.shell', 'enabled-extensions']).decode().strip()
exts = ast.literal_eval(out)
uuid = '$EXT_UUID'
if uuid not in exts:
    exts.append(uuid)
    subprocess.check_call(['gsettings', 'set', 'org.gnome.shell', 'enabled-extensions', str(exts)])
    print('✓ Added to gsettings enabled-extensions.')
else:
    print('✓ Already present in gsettings enabled-extensions.')
"

echo "Attempting to enable via gnome-extensions CLI..."
gnome-extensions enable "$EXT_UUID" 2>/dev/null || true

echo "=== Installation Complete ==="
echo "Note: If running GNOME on Wayland, log out and log back in (or press Alt+F2 > 'r' on X11)"
echo "for GNOME Shell to index the newly registered extension."
