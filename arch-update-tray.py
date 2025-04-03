#!/usr/bin/env python3
import sys
import os
import re
import subprocess
import time
import logging
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox, QInputDialog, QLineEdit
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
        self.logger.info(f"Environment: {os.environ}")
        Notify.init("Arch Update Tray")

        self.logger.info("Attempting sudoers setup")
        self.setup_sudoers()
        self.logger.info("Attempting yay config setup")
        self.setup_yay_config()

        self.logger.info("Initializing QApplication")
        self.app = QApplication(sys.argv)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.logger.error("System tray not available")
            sys.exit(1)
        
        self.logger.info("Setting up tray icon")
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
        self.logger.info(f"Icon paths: green={green_path}, red={red_path}, green_exists={os.path.exists(green_path)}, red_exists={os.path.exists(red_path)}")
        if not os.path.exists(green_path) or not os.path.exists(red_path):
            self.logger.warning("Icons not found, tray may be invisible")
        self.tray.setIcon(self.green_icon)
        self.tray.setToolTip("System is up to date")

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

    def setup_sudoers(self):
        sudoers_file = "/etc/sudoers.d/arch-update-tray"
        sudoers_content = f"{os.getlogin()} ALL=(ALL) NOPASSWD: /usr/bin/pacman -Syu --noconfirm, /usr/bin/pacman -Syu, /usr/bin/fwupdmgr refresh -y, /usr/bin/fwupdmgr get-updates -y, /usr/bin/fwupdmgr update -y\n"
        self.logger.info(f"Verifying sudoers setup for {sudoers_file}")
        try:
            contents = subprocess.run(["sudo", "-n", "cat", sudoers_file], capture_output=True, text=True, timeout=5)
            self.logger.info(f"Sudoers file contents: rc={contents.returncode}, stdout={contents.stdout}, stderr={contents.stderr}")
            test = subprocess.run(["sudo", "-n", "/usr/bin/pacman", "-Syu", "--noconfirm"], capture_output=True, text=True, timeout=5)
            self.logger.info(f"Sudo -n test: rc={test.returncode}, stdout={test.stdout}, stderr={test.stderr}")
            if test.returncode == 0:
                self.logger.info("Passwordless sudo works, no setup needed")
            else:
                self.logger.error(f"Sudo requires password: {test.stderr}")
                self.notify("Setup Required",
                        "Passwordless sudo needed for updates. Run in terminal:\n\n"
                        f"echo '{sudoers_content.strip()}' | sudo tee {sudoers_file} && sudo chmod 440 {sudoers_file}\n\n"
                        "Then restart your computer.")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Sudoers setup failed: {e}")
            self.notify("Setup Error",
                    f"Failed to configure sudoers: {e}\nRun manually:\n"
                    f"echo '{sudoers_content.strip()}' | sudo tee {sudoers_file} && sudo chmod 440 {sudoers_file}")
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"Sudo command timed out: {e}")
            self.notify("Setup Timeout", "Sudo setup took too long—run manually (see log)")

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
        try:
            test_cmd = ["sudo", "-n", "/usr/bin/pacman", "-Syu", "--noconfirm"]
            test = subprocess.run(test_cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            self.logger.info(f"Sudo test: rc={test.returncode}, stdout={test.stdout}, stderr={test.stderr}")
            if test.returncode != 0:
                self.logger.error(f"Sudo test failed: {test.stderr}")
                QMessageBox.critical(None, "Sudo Configuration Required",
                                    "This app needs password-less sudo for update commands.\n\n"
                                    "Run the following command to configure sudo:\n\n"
                                    "echo \"$USER ALL=(ALL) NOPASSWD: /usr/bin/pacman -Syu --noconfirm, /usr/bin/pacman -Syu, /usr/bin/pacman -Sy, /usr/bin/fwupdmgr refresh -y, /usr/bin/fwupdmgr get-updates -y, /usr/bin/fwupdmgr update -y\" | sudo tee /etc/sudoers.d/arch-update-tray && sudo chmod 440 /etc/sudoers.d/arch-update-tray\n\n"
                                    "Then restart your computer.")
                return
        except Exception as e:
            QMessageBox.critical(None, "Sudo Error", f"Error checking sudo permissions: {e}")
            return

        self.notify("Updates Starting", "System updates are being applied...")
        progress_window = QMessageBox(QMessageBox.Information, 
                                    "Updating System", 
                                    "Running system updates...\nThis may take several minutes.\n\nCheck the log at ~/.local/share/arch-update-tray.log for details.")
        progress_window.setStandardButtons(QMessageBox.NoButton)
        progress_window.show()

        update_success = True
        try:
            commands = [
                ["sudo", "pacman", "-Syu", "--noconfirm"],
                ["yay", "-Syua", "--noconfirm"] if subprocess.run(["which", "yay"]).returncode == 0 else None,
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

                    # Handle yay AUR builds
                    if "yay" in cmd and any(x in stdout.lower() for x in ["built", "building package(s)", "making package"]):
                        self.logger.info("AUR packages built—prompting for sudo to install.")
                        # Extract package name and version
                        updated_match = re.search(r"Updated version: (\S+)\s+([0-9a-zA-Z.]+)-\d+", stdout)
                        pkg_match = re.search(r"AUR Explicit \(\d+\): (\S+)-([0-9a-zA-Z.]+)-\d+", stdout)
                        self.logger.info(f"Raw updated_match: {updated_match.groups() if updated_match else None}")
                        self.logger.info(f"Raw pkg_match: {pkg_match.groups() if pkg_match else None}")
                        pkg_name = updated_match.group(1) if updated_match else (pkg_match.group(1) if pkg_match else "bitcoin-git")
                        latest_version = updated_match.group(2) if updated_match else (pkg_match.group(2) if pkg_match else "r44387")
                        self.logger.info(f"Detected package: {pkg_name}, version: {latest_version}")
                        aur_dir = os.path.expanduser(f"~/.cache/yay/{pkg_name}")
                        if os.path.exists(aur_dir):
                            pkg_files = [f for f in os.listdir(aur_dir) if f.endswith(".pkg.tar.zst") and latest_version in f]
                            self.logger.info(f"Found package files: {pkg_files}")
                            if pkg_files:
                                password, ok = QInputDialog.getText(None, "Sudo Password", "Enter your sudo password to install AUR updates:", QLineEdit.Password)
                                if ok and password:
                                    install_cmd = ["sudo", "-S", "pacman", "-U", "--noconfirm"] + [os.path.join(aur_dir, pkg) for pkg in pkg_files]
                                    self.logger.info(f"Running AUR install: {' '.join(install_cmd)}")
                                    process = subprocess.Popen(install_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                                    stdout, stderr = process.communicate(input=password + "\nY\n")
                                    self.logger.info(f"AUR install: stdout={stdout}, stderr={stderr}, rc={process.returncode}")
                                    if process.returncode != 0:
                                        self.logger.warning(f"AUR install failed: {stderr}")
                                        QMessageBox.warning(None, "AUR Install Failed", "Failed to install AUR updates—check log or run 'yay -U' manually.")
                                        update_success = False
                                    else:
                                        self.logger.info("AUR updates installed successfully.")
                                else:
                                    self.logger.info("User canceled AUR install.")
                                    QMessageBox.information(None, "AUR Install Skipped", "AUR updates built but not installed—run 'yay -U' manually if desired.")
                                    update_success = False
                            else:
                                self.logger.warning(f"No AUR package files found for version {latest_version} in {aur_dir}.")
                                update_success = False
                        else:
                            self.logger.warning(f"AUR build directory {aur_dir} not found.")
                            update_success = False
                    elif process.returncode != 0:
                        if "sudo" in cmd and "password" in stderr.lower():
                            self.logger.error(f"Sudo failed for {cmd}: {stderr}")
                            QMessageBox.critical(None, "Sudo Error",
                                                "Password required for core updates. Add to /etc/sudoers.d/arch-update-tray:\n"
                                                "michael ALL=(ALL) NOPASSWD: /usr/bin/pacman -Syu --noconfirm, /usr/bin/pacman -Syu, /usr/bin/pacman -Sy, /usr/bin/fwupdmgr refresh -y, /usr/bin/fwupdmgr get-updates -y, /usr/bin/fwupdmgr update -y")
                            update_success = False
                            break
                        elif not any(x in stdout.lower() + stderr.lower() for x in ["no updates available", "system is up to date", "nothing to do", "metadata is up to date"]):
                            self.logger.warning(f"Command failed: {' '.join(cmd)} - {stderr}")
                            update_success = False
                    time.sleep(1)
                except Exception as e:
                    self.logger.error(f"Error running {cmd}: {e}")
                    update_success = False
        finally:
            progress_window.close()
            self.check_updates(show_notification=True)
        if update_success:
            self.notify("Updates Complete", "System has been updated successfully")
        else:
            self.notify("Update Issues", "Some updates may have failed. Check the log for details.")


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
