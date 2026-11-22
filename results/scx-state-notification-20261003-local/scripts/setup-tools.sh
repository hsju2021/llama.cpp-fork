set -eu
cd /home/hs/scx-state-validation/toolchain/debs
for pkg in *.deb; do dpkg-deb -x "$pkg" ../root; done
export LD_LIBRARY_PATH=/home/hs/scx-state-validation/toolchain/root/usr/lib/x86_64-linux-gnu
../root/usr/bin/cmake --version
../root/usr/bin/clang-18 --version
