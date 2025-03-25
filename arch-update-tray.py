import sys
import subprocess
import time
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PyQt5.QtGui import QIcon 
from PyQt5.QtCore import QTimer

class ArchUpdateTray:
    def __init__(self):
        self.app = QApplication(sys.argv)
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(None, "Error", "System tray is not available.")
            sys.exit(1)

        self.tray = QSystemTrayIcon()
        self.menu =QMenu()
        self.updates_available = False

        # Load icons (fallback to generic if theme icons are missing)
        self.green_icon = QIcon.fromTheme("system-software-update", QIcon("update-green.png"))
        self.red_icon = QIcon.fromTheme("software-update-available", QIcon("update-red.png"))
        self.tray.setIcon(self.green_icon)

        # Menu items
        self.update_action = self.menu.addAction("Run Updates")
        self.update_action.triggered.conect(self.run_updates)
        self.menu.addAction("Check Updates", self.check_updates)
        self.menu.addAction("Quit", self.quit_app)
        self.tray.setContectMenu(self.menu)

        # Show tray icon   
        self.tray.show()
        self.tray.setToolTip("Arch Update Tray")

        #Periodic update check (every 30 min)
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_updates)
        self.timer.start(1800000) # 30 min in ms  
        self.check_updates()

    def check_updates(self):
        """Check for available updates and update the tray icon."""
        try:
            #pacman
            pacman_check = subprocess.run(["pacman", "-Qu"], capture_output=True, text=True)
            pacman_updates = len(pacman_check.stdout.strip().splitlines()) > 0
            
            # Check yay updates (optional, skip if yay non installed)
            yay_updates = False
            if subprocess.run(["which", "yay"], capture_output=True).returncode == 0:
                yay_check = subprocess.run(["yay", "-Qu"], capture_output=True, text=True)
                yay_updates = len(yay_check.stdout.strip().splitlines()) > 0

            #Check firmware updates (optional, skip if fwupd not installed)
            fwupd_updates = False
            if subprocess.run(["which", "fwupdmgr"], capture_output=True).returncode == 0:
                fwupd_check = subprocess.run(["fwupdmgr", "get-updates"], capture_output=True, text=True)
                fwupd_updates = "No updates available" not in fwupd_check.stdout

            self.updates_available = pacman_updates or yay_updates or fwupd_updates
            self.tray.setIcon(self.red_icon if self.updates_available else self.green_icon)
            self.Tray.setToolTip("Updates Available" if self.updates_available else "System is up to date")
        except Exception as e:
            QMessageBox.warning(None, "Error", f"Failed to check for updates: {e}")

    def run_updates(self):
        """Run system updates."""
        commands = [
            ["sudo", "pacman", "-Syu", "--noconfirm"],
            ["yay", "-Syu", "--noconfirm"] if subprocess.run(["which", "yay"].returncode == 0 else None,
            ["sudo", "fwupdmgr", "refresh", "-y"] if subprocess.run(["which", "fwupdmgr"].returncode == 0 else None,
            ["sudo", "fwupdmgr", "get-updates", "-y"] if subprocess.run(["which", "fwupdmgr"].returncode == 0 else None,
            ["sudo", "fwupdmgr", "update", "-y"] if subprocess.run(["which", "fwupdmgr"].returncode == 0 else None,
        ]
        for cmd in [c for c in commands if c]:
            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate()
                if process.returncode != 0:
                    QMessageBox.warning(None, "Update Error", f"Command {' '.join(cmd)} failed:\n{stderr}")
                time.sleep(1)
            except Exception as e:
                QMessageBox.critical(None, "Update Failed", f"Error running {cmd}: {e}")
        self.check_updates() # Re-check for updates after running updates

    def quit_app(self):
        """Quit the application."""
        self.tray.hide()
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    app = ArchUpdateTray()
    app.run()
