set -eu
root=/home/hs/scx-state-validation
archive='/mnt/c/Users/HS/.codex/worktrees/182f/Graduation Project/results/scx-state-notification-20261003-local'
test ! -e "$archive"
mkdir -p "$archive/logs" "$archive/scripts"
cp "$root/logs"/provider-*-tests.log "$root/logs"/provider-*-backend.log "$root/logs"/provider-*-cmake-cache.txt "$archive/logs/"
cp "$root/logs/provider-on-openmp-clean-build.log" "$archive/logs/"
cp "$root/logs"/provider-off-*-build.log "$root/logs/provider-on-native-build.log" "$root/logs"/provider-*-final-build.log "$archive/logs/"
cp "$root/logs/symbol-validation.json" "$archive/"
cp "$root/vmlinux-source.txt" "$archive/"
cp /mnt/c/Users/HS/AppData/Local/Temp/scx-state-validation-20261003/*.sh "$archive/scripts/"
uname -a > "$archive/environment.txt"
"$root/toolchain/root/usr/bin/cmake" --version >> "$archive/environment.txt" 2>&1 || true
cc --version >> "$archive/environment.txt"