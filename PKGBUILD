# Maintainer: Michael Calabrese <nw.calabrese@proton.me>
pkgname=arch-update-tray
pkgver=1.0.0
pkgrel=1
pkgdesc="A system tray application for managing Arch Linux updates (pacman, yay, fwupd)"
arch=('any')
url="https://github.com/Mccalabrese/arch-update-tray"
license=('GPL3')
depends=('python' 'python-pyqt5' 'pacman' 'sudo' 'python-gobject' 'libnotify')
optdepends=('yay: for AUR updates' 'fwupd: for firmware updates')
source=("$pkgname.py" "update-green.png" "update-red.png" "$pkgname.desktop")
sha256sums=('bf9fe50e09078fb197b39924d6a280ceeeb41e294bd955999d2f04a3fce33554'
            '63d4bb590e640a26affe2d082634488d2393a5ce3a964e40e5e8be59e2caeaca'
            '8ceb1f920bdee453f70f46145c9ec389138b88de73763b3732887cc8771f38e4'
            '4bdd7715578c6afeeda38e68e1d8a9ba5fa0d0741461b1b5ea4a4880e1d6d6d2')
package() {
    # Install the Python script
    install -Dm755 "$srcdir/$pkgname.py" "$pkgdir/usr/bin/$pkgname"

    # Install icons
    install -Dm644 "$srcdir/update-green.png" "$pkgdir/usr/share/icons/hicolor/16x16/apps/$pkgname-green.png"
    install -Dm644 "$srcdir/update-red.png" "$pkgdir/usr/share/icons/hicolor/16x16/apps/$pkgname-red.png"

    # Install desktop file for autostart
    install -Dm644 "$srcdir/$pkgname.desktop" "$pkgdir/usr/share/applications/$pkgname.desktop"

    echo "First run may prompt for sudo to configure /etc/sudoers.d/arch-update-tray"
}
