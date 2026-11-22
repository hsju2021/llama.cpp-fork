set -eu
export SCX_TOOLS=/home/hs/scx-state-validation/toolchain/root/usr
export LD_LIBRARY_PATH="$SCX_TOOLS/lib/x86_64-linux-gnu"
export PATH="$SCX_TOOLS/bin:$PATH"
cmake --version
clang-18 --version
command -v rsync
mkdir -p /home/hs/scx-state-validation/provider
cd /home/hs/scx-state-validation/provider
tar -xf /mnt/c/Users/HS/AppData/Local/Temp/scx-state-validation-20261003/provider-base.tar
cmake -S . -B ../build-on-openmp -G Ninja -DCMAKE_BUILD_TYPE=Release -DLLAMA_SCX_PHASE_TRACE=ON -DGGML_OPENMP=ON -DGGML_NATIVE=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=ON -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TOOLS=ON -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_UI=OFF -DLLAMA_BUILD_APP=OFF
cmake --build ../build-on-openmp --target llama-server test-arg-parser test-compute-profile test-backend-ops -j 4