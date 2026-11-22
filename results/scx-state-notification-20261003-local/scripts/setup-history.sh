set -eu
root=/home/hs/scx-state-validation
if [ ! -d "$root/scheduler/.git" ]; then
    git clone --no-checkout --shared /mnt/c/Users/HS/Documents/llama-scheduler "$root/scheduler-history"
    cp -a "$root/scheduler-history/.git" "$root/scheduler/.git"
fi