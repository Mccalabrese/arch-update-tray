#!/usr/bin/env python3
import sys
import os
import subprocess
import time
import logging
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PyQt5.QtGui import QIcon, QCursor
from PyQt5.QtCore import QTimer
import gi
gi.require_version('Notify', '0.7')
from gi.repository import Notify

class ArchUpdateTray:
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.expanduser("~/.local/share/arch-update-tray.log")),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('arch-update-tray')
        self.logger.info("Starting Arch Update Tray")

        self.app = QApplication(sys.argv)
        self.logger.info(f"PID: {os.getpid()}, DISPLAY: {os.environ.get('DISPLAY')}, WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY')}")
        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("System tray not available")
            QMessageBox.critical(None, "Error", "System tray is not available.")
            sys.exit(1)

        self.tray = QSystemTrayIcon()
        self.menu = QMenu()
        self.updates_available = False

        # Load icons with absolute paths
        icon_dir = "/usr/share/icons/hicolor/16x16/apps"
        if os.path.exists(os.path.join(os.path.dirname(__file__), "update-green.png")):
            # Development mode - use local icons
            green_path = os.path.join(os.path.dirname(__file__), "update-green.png")
            red_path = os.path.join(os.path.dirname(__file__), "update-red.png")
        else:
            # Installed mode - use system icons
            green_path = f"{icon_dir}/arch-update-tray-green.png"
            red_path = f"{icon_dir}/arch-update-tray-red.png"
        self.green_icon = QIcon(green_path)
        self.red_icon = QIcon(red_path)
        print(f"Green icon exists: {os.path.exists(green_path)}, Red icon exists: {os.path.exists(red_path)}")
        if not os.path.exists(green_path) or not os.path.exists(red_path):
            print("Warning: Icons not found, tray may be invisible")
        self.tray.setIcon(self.green_icon)
        self.tray.setToolTip("System is up to date")
        self.tray.show()

        # Menu items
        self.update_action = self.menu.addAction("Run Updates")
        self.update_action.triggered.connect(self.run_updates)
        self.menu.addAction("Check Updates", lambda: self.check_updates(show_notification=True))
        self.menu.addAction("Settings", self.show_settings)
        self.menu.addAction("Quit", self.quit_app)
        self.tray.setContextMenu(self.menu)

        # Show tray icon
        self.tray.show()
        self.tray.setToolTip("Arch Update Tray")

        # Periodic update check (every 30 min)
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_updates)
        self.timer.start(1800000)  # 30 min in ms
        self.check_updates()

        Notify.init("Arch Update Tray")

    def check_updates(self, show_notification=False):
        """Check for available updates and update the tray icon."""
        try:
            pacman_check = subprocess.run(["pacman", "-Qu"], capture_output=True, text=True)
            pacman_updates = len(pacman_check.stdout.strip().splitlines()) > 0 and pacman_check.returncode == 0

            yay_updates = False
            if subprocess.run(["which", "yay"]).returncode == 0:
                yay_check = subprocess.run(["yay", "-Qu"], capture_output=True, text=True)
                yay_updates = len(yay_check.stdout.strip().splitlines()) > 0 and yay_check.returncode == 0

            fwupd_updates = False
            if subprocess.run(["which", "fwupdmgr"]).returncode == 0:
                fwupd_check = subprocess.run(["fwupdmgr", "get-updates"], capture_output=True, text=True)
                fwupd_updates = fwupd_check.returncode == 0 and "No updates available" not in fwupd_check.stdout

            self.updates_available = pacman_updates or yay_updates or fwupd_updates
            self.tray.setIcon(self.red_icon if self.updates_available else self.green_icon)
            self.tray.setToolTip("Updates Available" if self.updates_available else "System is up to date")
            
            if show_notification:
                self.notify("Update Check Complete", 
                           "Updates available" if self.updates_available else "System is up to date",
                           "arch-update-tray-red" if self.updates_available else "arch-update-tray-green")
        except Exception as e:
            self.logger.error(f"Check updates error: {e}")
            QMessageBox.warning(None, "Error", f"Failed to check for updates: {e}")

    def run_updates(self):
        """Run system updates."""
        # First check if we can run sudo without password
        try:
            test = subprocess.run(["sudo", "-n", "true"], capture_output=True)
            if test.returncode != 0:
                QMessageBox.critical(None, "Sudo Configuration Required",
                                  "This app needs password-less sudo for update commands.\n\n"
                                  "Run the following command to configure sudo:\n\n"
                                  "echo \"$USER ALL=(ALL) NOPASSWD: /usr/bin/pacman -Syu --noconfirm, /usr/bin/fwupdmgr refresh -y, /usr/bin/fwupdmgr get-updates -y, /usr/bin/fwupdmgr update -y\" | sudo tee /etc/sudoers.d/arch-update-tray\n\n"
                                  "For AUR updates, also configure yay to not require sudo password.")
                return
        except Exception as e:
            QMessageBox.critical(None, "Sudo Error", f"Error checking sudo permissions: {e}")
            return
            
        self.notify("Updates Starting", "System updates are being applied...", self.red_icon)
        
        # Create a simple progress dialog
        progress_window = QMessageBox(QMessageBox.Information, 
                                     "Updating System", 
                                     "Running system updates...\nThis may take several minutes.\n\nCheck the log at ~/.local/share/arch-update-tray.log for details.")
        progress_window.setStandardButtons(QMessageBox.NoButton)
        progress_window.show()
        
        update_success = True
        try:
            commands = [
                ["sudo", "pacman", "-Syu", "--noconfirm"],
                ["yay", "-Syu", "--noconfirm"] if subprocess.run(["which", "yay"]).returncode == 0 else None,
                ["sudo", "fwupdmgr", "refresh", "-y"] if subprocess.run(["which", "fwupdmgr"]).returncode == 0 else None,
                ["sudo", "fwupdmgr", "get-updates", "-y"] if subprocess.run(["which", "fwupdmgr"]).returncode == 0 else None,
                ["sudo", "fwupdmgr", "update", "-y"] if subprocess.run(["which", "fwupdmgr"]).returncode == 0 else None,
            ]
            for cmd in [c for c in commands if c]:
                try:
                    self.logger.info(f"Running command: {' '.join(cmd)}")
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    stdout, stderr = process.communicate()
                    if process.returncode != 0:
                        if "password" in stderr.lower():
                            QMessageBox.critical(None, "Sudo Error",
                                                "Password required. Add to /etc/sudoers via 'sudo visudo':\n"
                                                "<username> ALL=(ALL) NOPASSWD: /usr/bin/pacman -Syu, /usr/bin/yay -Syu, "
                                                "/usr/bin/fwupdmgr refresh, /usr/bin/fwupdmgr get-updates, /usr/bin/fwupdmgr update")
                        elif "no updates available" not in stderr.lower() and "system is up to date" not in stdout.lower():
                            QMessageBox.warning(None, "Update Error", f"Command {' '.join(cmd)} failed:\n{stderr}")
                    time.sleep(1)
                except Exception as e:
                    update_success = False
                    self.logger.error(f"Error running {cmd}: {e}")
        finally:
            progress_window.close()
            
        # Notify about completion
        if update_success:
            self.notify("Updates Complete", "System has been updated successfully", self.green_icon)
        else:
            self.notify("Update Issues", "Some updates may have failed. Check the application log for details.", self.red_icon)

    def notify(self, title, message, icon_name=None):
        """Send a desktop notification."""
        notification = Notify.Notification.new(title, message)
        if icon_name:
            notification.set_icon_name(icon_name)
        notification.show()

    def quit_app(self):
        """Quit the application."""
        self.tray.hide()
        self.app.quit()

    def show_settings(self):
        intervals = {"30 minutes": 30, "1 hour": 60, "2 hours": 120, "4 hours": 240, "Daily": 1440}
        current_interval = self.timer.interval() // 60000  # Convert ms to minutes
        
        # Find closest match in our predefined intervals
        current_setting = next((k for k, v in intervals.items() if v == current_interval), "30 minutes")
        
        menu = QMenu()
        for name, minutes in intervals.items():
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name == current_setting)
            action.triggered.connect(lambda checked, m=minutes: self.set_check_interval(m))
        
        # Position menu under the tray icon
        menu.exec_(QCursor.pos())

    def set_check_interval(self, minutes):
        self.timer.setInterval(minutes * 60000)  # Convert minutes to ms
        self.notify("Check Interval Updated", f"Updates will be checked every {minutes} minutes")

    def run(self):
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    app = ArchUpdateTray()
    app.run()
