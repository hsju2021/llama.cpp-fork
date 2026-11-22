set -eu
root=/home/hs/scx-state-validation
curl -fLsS https://raw.githubusercontent.com/sched-ext/scx/e37ab1fd7ec09505c33beaefdc128bab2d582660/scheds/vmlinux/arch/x86/vmlinux-v6.18-rc4-g6146a0f1dfae.h -o "$root/vmlinux.h"
printf '%s\n' 'https://raw.githubusercontent.com/sched-ext/scx/e37ab1fd7ec09505c33beaefdc128bab2d582660/scheds/vmlinux/arch/x86/vmlinux-v6.18-rc4-g6146a0f1dfae.h' > "$root/vmlinux-source.txt"
mkdir -p "$root/fixture-kernel/include/uapi/linux" "$root/scheduler/build/include"
curl -fLsS https://raw.githubusercontent.com/torvalds/linux/v6.17/include/uapi/linux/sched.h -o "$root/fixture-kernel/include/uapi/linux/sched.h"
cp "$root/vmlinux.h" "$root/scheduler/build/include/vmlinux.h"
rsync -a --exclude=.git --exclude=build --exclude=.deps --exclude=results /mnt/c/Users/HS/Documents/llama-scheduler/ "$root/scheduler/"
export SCX_TOOLS="$root/toolchain/root/usr"
export LD_LIBRARY_PATH="$SCX_TOOLS/lib/x86_64-linux-gnu"
export PATH="$SCX_TOOLS/bin:$PATH"
cd "$root/scheduler"
make -j4 VMLINUX_BTF="$root/vmlinux.h" CLANG=clang-18 KERNEL_HEADERS="$root/fixture-kernel" BPF_CFLAGS="-target bpf -D__TARGET_ARCH_x86 -O2 -g -Wall -Werror -Wno-missing-declarations -Ibuild/include -Iinclude -I$SCX_TOOLS/include -I/usr/include/x86_64-linux-gnu" USER_CFLAGS="-O2 -g -Wall -Wextra -Werror -std=gnu11 -Iinclude -I$SCX_TOOLS/include" USER_LDLIBS="-L$SCX_TOOLS/lib/x86_64-linux-gnu -lbpf -lelf -lz"