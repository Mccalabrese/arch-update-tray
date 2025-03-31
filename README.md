# Arch Update Tray
A system tray app for managing Arch Linux updates (`pacman`, `yay`, `fwupd`).

## Features
- Checks for updates every 30 minutes (configurable).
- Runs updates with one click (`pacman -Syu`, `yay -Syu`, `fwupdmgr update`).
- Desktop notifications for update status.
- Tray icon: green (up to date), red (updates available).

## Installation
1. Clone: `git clone https://github.com/Mccalabrese/arch-update-tray.git`
2. Build: `cd arch-update-tray && makepkg -si`
3. Run: App menu → "Arch Update Tray" (or `/usr/bin/arch-update-tray`)

## First Run
- Prompts for sudo password to configure `/etc/sudoers.d/arch-update-tray`—enables passwordless updates.
- Creates `~/.config/yay/config.json` for `yay` (if installed).

## Dependencies
- Required: `python`, `python-pyqt5`, `pacman`, `sudo`, `python-gobject`, `libnotify`
- Optional: `yay` (AUR), `fwupd` (firmware)

## Troubleshooting
- **Log**: `~/.local/share/arch-update-tray.log`
- **Sudo fails**: Run `sudo visudo -f /etc/sudoers.d/arch-update-tray` and add: