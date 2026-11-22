#include "llama.h"

#include "../src/llama-context.h"

int main() {
    const auto options = llama_decode_default_options();
    GGML_ASSERT(options.compute_profile == LLAMA_COMPUTE_PROFILE_AUTO);

    GGML_ASSERT(llama_compute_profile_resolve(LLAMA_COMPUTE_PROFILE_AUTO,       0) == LLAMA_COMPUTE_PROFILE_GENERATION);
    GGML_ASSERT(llama_compute_profile_resolve(LLAMA_COMPUTE_PROFILE_AUTO,       1) == LLAMA_COMPUTE_PROFILE_GENERATION);
    GGML_ASSERT(llama_compute_profile_resolve(LLAMA_COMPUTE_PROFILE_AUTO,       2) == LLAMA_COMPUTE_PROFILE_BATCH);
    GGML_ASSERT(llama_compute_profile_resolve(LLAMA_COMPUTE_PROFILE_GENERATION, 1) == LLAMA_COMPUTE_PROFILE_GENERATION);
    GGML_ASSERT(llama_compute_profile_resolve(LLAMA_COMPUTE_PROFILE_GENERATION, 8) == LLAMA_COMPUTE_PROFILE_GENERATION);
    GGML_ASSERT(llama_compute_profile_resolve(LLAMA_COMPUTE_PROFILE_BATCH,      1) == LLAMA_COMPUTE_PROFILE_BATCH);
    GGML_ASSERT(llama_compute_profile_resolve(LLAMA_COMPUTE_PROFILE_BATCH,      8) == LLAMA_COMPUTE_PROFILE_BATCH);

    llama_decode_options invalid_options = options;
    invalid_options.compute_profile = static_cast<llama_compute_profile>(3);

    GGML_ASSERT(!llama_compute_profile_is_valid(invalid_options.compute_profile));
    // Invalid options must be rejected before the context is accessed.
    alignas(64) unsigned char dummy_ctx[64] = {};
    auto * fake_ctx = reinterpret_cast<llama_context *>(dummy_ctx);
    GGML_ASSERT(llama_decode_with_options(fake_ctx, {}, invalid_options) == -1);
    GGML_ASSERT(llama_decode_with_options(nullptr, {}, options) == -1);
    GGML_ASSERT(llama_decode(nullptr, {}) == -1);
}
