#include "server-scx.h"

#ifdef LLAMA_SCX_PHASE_TRACE

extern "C" {

// Distinct nop sequences prevent identical-code folding from merging uprobe symbol addresses.
__attribute__((noinline, used, visibility("default")))
void llama_scx_phase_set_v2(const server_scx_state_v2 * event) {
    __asm__ __volatile__("nop; nop; nop" : : "r"(event) : "memory");
}

__attribute__((noinline, used, visibility("default")))
void llama_scx_decode_begin_v1(const server_scx_event * event) {
    __asm__ __volatile__("nop" : : "r"(event) : "memory");
}

__attribute__((noinline, used, visibility("default")))
void llama_scx_decode_end_v1(const server_scx_event * event) {
    __asm__ __volatile__("nop; nop" : : "r"(event) : "memory");
}

} // extern "C"

#endif
