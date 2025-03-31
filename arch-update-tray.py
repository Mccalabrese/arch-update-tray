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
        self.setup_sudoers()
        self.setup_yay_config()
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

    def setup_sudoers(self):
        sudoers_file = "/etc/sudoers.d/arch-update-tray"
        sudoers_content = f"{os.getlogin()} ALL=(ALL) NOPASSWD: /usr/bin/pacman -Syu --noconfirm, /usr/bin/pacman -Syu, /usr/bin/fwupdmgr refresh -y, /usr/bin/fwupdmgr get-updates -y, /usr/bin/fwupdmgr update -y\n"
    if not os.path.exists(sudoers_file):
        try:
            subprocess.run(["sudo", "tee", sudoers_file], input=sudoers_content, text=True, check=True)
            subprocess.run(["sudo", "chmod", "440", sudoers_file], check=True)
            self.logger.info("Sudoers configured")
            self.notify("Setup", "Sudo permissions set—restart app if needed")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Sudoers setup failed: {e}")
            QMessageBox.critical(None, "Setup Error", f"Run manually:\necho '{sudoers_content.strip()}' | sudo tee {sudoers_file} && sudo chmod 440 {sudoers_file}")

    def setup_yay_config(self):
        yay_dir = os.path.expanduser("~/.config/yay")
        yay_file = f"{yay_dir}/config.json"
        yay_content = '{"sudoflags": "-n"}'
        if not os.path.exists(yay_file):
            try:
                os.makedirs(yay_dir, exist_ok=True)
                with open(yay_file, "w") as f:
                    f.write(yay_content)
                self.logger.info("Yay config set")
            except Exception as e:
                self.logger.error(f"Yay config failed: {e}")
                QMessageBox.warning(None, "Yay Error", f"Create {yay_file} with:\n{yay_content}")



    def check_updates(self, show_notification=False):
        """Check for available updates and update the tray icon."""
        try:
            pacman_check = subprocess.run(["pacman", "-Qu"], capture_output=True, text=True)
            pacman_updates = len(pacman_check.stdout.strip().splitlines()) > 0 and pacman_check.returncode == 0
            print(f"Pacman: updates={pacman_updates}")

            yay_updates = False
            if subprocess.run(["which", "yay"]).returncode == 0:
                print(subprocess.run(["which", "yay"], capture_output=True, text=True).stdout.strip())
                yay_check = subprocess.run(["yay", "-Qu"], capture_output=True, text=True)
                yay_updates = len(yay_check.stdout.strip().splitlines()) > 0 and yay_check.returncode == 0
                print(f"Yay: updates={yay_updates}")

            fwupd_updates = False
            if subprocess.run(["which", "fwupdmgr"]).returncode == 0:
                print(subprocess.run(["which", "fwupdmgr"], capture_output=True, text=True).stdout.strip())
                fwupd_check = subprocess.run(["fwupdmgr", "get-updates"], capture_output=True, text=True)
                fwupd_updates = fwupd_check.returncode == 0 and "No updates available" not in fwupd_check.stdout
                print(f"FWUpd: updates={fwupd_updates}")

            self.updates_available = pacman_updates or yay_updates or fwupd_updates
            self.tray.setIcon(self.red_icon if self.updates_available else self.green_icon)
            self.tray.setToolTip("Updates Available" if self.updates_available else "System is up to date")
            
            if show_notification:
                self.notify("Update Check Complete", 
                           "Updates available" if self.updates_available else "System is up to date")
        except Exception as e:
            self.logger.error(f"Check updates error: {e}")
            QMessageBox.warning(None, "Error", f"Failed to check for updates: {e}")

    def run_updates(self):
        """Run system updates."""
        # First check if we can run sudo without password by trying the actual command
        try:
            # Force test to use /usr/bin/pacman to match the sudoers path exactly
            test_cmd = ["/usr/bin/sudo", "-n", "/usr/bin/pacman", "--version"]
            test = subprocess.run(test_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            self.logger.info(f"Sudo test: rc={test.returncode}, stdout={test.stdout}, stderr={test.stderr}")
            if test.returncode != 0:
                self.logger.error(f"Sudo test failed: {test.stderr}")
                QMessageBox.critical(None, "Sudo Error", f"Sudo failed: {test.stderr}\nCheck /etc/sudoers.d/arch-update-tray")
            
            if test.returncode != 0:
                QMessageBox.critical(None, "Sudo Configuration Required",
                                  "This app needs password-less sudo for update commands.\n\n"
                                  "Run the following command to configure sudo:\n\n"
                                  "echo \"$USER ALL=(ALL) NOPASSWD: /usr/bin/pacman -Syu --noconfirm, /usr/bin/pacman -Syu, /usr/bin/fwupdmgr refresh -y, /usr/bin/fwupdmgr get-updates -y, /usr/bin/fwupdmgr update -y\" | sudo tee /etc/sudoers.d/arch-update-tray\n\n"
                                  "Then reboot or run: sudo systemctl restart sudo\n\n"
                                  "For AUR updates, also configure yay to not require sudo password in /etc/yay.conf (add: sudoflags = -n)")
                return
        except Exception as e:
            QMessageBox.critical(None, "Sudo Error", f"Error checking sudo permissions: {e}")
            return
            
        self.notify("Updates Starting", "System updates are being applied...")
        
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
                    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    stdout, stderr = process.communicate(input="y\n")
                    self.logger.info(f"Command output: stdout={stdout}, stderr={stderr}, rc={process.returncode}")
                    if process.returncode != 0:
                        if "password" in stderr.lower():
                            self.logger.error(f"Sudo failed for {cmd}: {stderr}")
                            QMessageBox.critical(None, "Sudo Error",
                                                "Password required. Add to /etc/sudoers.d/arch-update-tray via 'sudo visudo -f /etc/sudoers.d/arch-update-tray':\n"
                                                "michael ALL=(ALL) NOPASSWD: /usr/bin/pacman -Syu --noconfirm, /usr/bin/pacman -Syu, /usr/bin/fwupdmgr refresh -y, /usr/bin/fwupdmgr get-updates -y, /usr/bin/fwupdmgr update -y")
                        elif not any(x in stdout.lower() + stderr.lower() for x in ["no updates available", "system is up to date", "nothing to do", "metadata is up to date"]):
                            QMessageBox.warning(None, "Update Error", f"Command {' '.join(cmd)} failed:\n{stderr}")
                            update_success = False
                    time.sleep(1)
                except Exception as e:
                    update_success = False
                    self.logger.error(f"Error running {cmd}: {e}")
        finally:
            progress_window.close()
            self.check_updates(show_notification=True)
        # Notify about completion
        if update_success:
            self.notify("Updates Complete", "System has been updated successfully")
        else:
            self.notify("Update Issues", "Some updates may have failed. Check the application log for details.")

    def notify(self, title, message):
        """Send a desktop notification."""
        try:
            notification = Notify.Notification.new(title, message, "dialog-information")
            notification.set_urgency(Notify.Urgency.NORMAL)
            notification.show()
        except Exception as e:
            self.logger.error(f"Notification error: {e}")
            # If notification fails, at least log the message
            self.logger.info(f"Notification: {title} - {message}")

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
