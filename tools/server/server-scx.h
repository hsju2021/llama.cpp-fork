#pragma once

#include <cstdint>
#include <cstddef>
#include <exception>

struct server_scx_state_v2 {
    uint32_t version;
    uint32_t phase;
    uint32_t active;
    uint32_t reserved;
    uint64_t run_id;
    uint64_t sequence;
};
static_assert(sizeof(server_scx_state_v2) == 32, "SCX state ABI v2");
static_assert(offsetof(server_scx_state_v2, version) == 0, "SCX version offset");
static_assert(offsetof(server_scx_state_v2, phase) == 4, "SCX phase offset");
static_assert(offsetof(server_scx_state_v2, active) == 8, "SCX active offset");
static_assert(offsetof(server_scx_state_v2, reserved) == 12, "SCX reserved offset");
static_assert(offsetof(server_scx_state_v2, run_id) == 16, "SCX run_id offset");
static_assert(offsetof(server_scx_state_v2, sequence) == 24, "SCX sequence offset");

class server_scx_state_publisher {
    uint64_t publisher_run_id = 0;
    uint64_t sequence = 0;
    uint32_t last_phase = 0;
    bool last_active = false;
public:
    template<typename Emit>
    bool publish(uint64_t run_id, uint32_t phase, bool active, Emit emit) {
        if (!active) { phase = 0; }
        if (!run_id) { return false; }
        if (!publisher_run_id) { publisher_run_id = run_id; }
        if (run_id != publisher_run_id || (last_phase == phase && last_active == active)) { return false; }
        server_scx_state_v2 event { 2, phase, uint32_t(active), 0, run_id, ++sequence };
        emit(&event);
        last_phase = phase;
        last_active = active;
        return true;
    }
    template<typename Emit>
    bool idle(uint64_t run_id, Emit emit) { return publish(run_id, 0, false, emit); }
    template<typename Emit>
    bool reconcile(uint64_t run_id, bool processing, Emit emit) {
        return processing ? false : idle(run_id, emit);
    }
};

template<typename Reconcile, typename Clear>
class server_scx_reconcile_scope {
    Reconcile reconcile;
    Clear clear;
    int exceptions = std::uncaught_exceptions();
public:
    server_scx_reconcile_scope(Reconcile reconcile, Clear clear) : reconcile(reconcile), clear(clear) { reconcile(); }
    server_scx_reconcile_scope(const server_scx_reconcile_scope &) = delete;
    server_scx_reconcile_scope & operator=(const server_scx_reconcile_scope &) = delete;
    ~server_scx_reconcile_scope() {
        if (std::uncaught_exceptions() > exceptions) { clear(); }
        else { reconcile(); }
    }
};

inline uint32_t server_scx_classify_phase(int32_t n_prefill, int32_t n_decode, int32_t n_unknown) {
    if (n_unknown) { return 0; }
    if (n_prefill && n_decode) { return 3; }
    if (n_prefill) { return 1; }
    if (n_decode) { return 2; }
    return 0;
}

// Keep the v1 layout in sync with llama-scheduler/include/llama_phase.h.
struct server_scx_event {
    uint64_t version;
    uint64_t run_id;
    uint64_t call_id;
    uint64_t retry;
    uint64_t phase;
    uint64_t profile;
    uint64_t n_prefill;
    uint64_t n_decode;
    uint64_t n_unknown;
    int64_t result;
};
static_assert(sizeof(server_scx_event) == 80, "SCX phase ABI v1");
static_assert(offsetof(server_scx_event, version) == 0, "SCX v1 version offset");
static_assert(offsetof(server_scx_event, run_id) == 8, "SCX v1 run_id offset");
static_assert(offsetof(server_scx_event, call_id) == 16, "SCX v1 call_id offset");
static_assert(offsetof(server_scx_event, retry) == 24, "SCX v1 retry offset");
static_assert(offsetof(server_scx_event, phase) == 32, "SCX v1 phase offset");
static_assert(offsetof(server_scx_event, profile) == 40, "SCX v1 profile offset");
static_assert(offsetof(server_scx_event, n_prefill) == 48, "SCX v1 n_prefill offset");
static_assert(offsetof(server_scx_event, n_decode) == 56, "SCX v1 n_decode offset");
static_assert(offsetof(server_scx_event, n_unknown) == 64, "SCX v1 n_unknown offset");
static_assert(offsetof(server_scx_event, result) == 72, "SCX v1 result offset");


#ifdef LLAMA_SCX_PHASE_TRACE
#include "llama.h"

extern "C" {
void llama_scx_phase_set_v2(const server_scx_state_v2 * event);

__attribute__((noinline, used, visibility("default")))
void llama_scx_phase_set_v2(const server_scx_state_v2 * event) {
    __asm__ __volatile__("nop; nop; nop" : : "r"(event) : "memory");
}

void llama_scx_decode_begin_v1(const server_scx_event * event);
void llama_scx_decode_end_v1(const server_scx_event * event);

__attribute__((noinline, used, visibility("default")))
void llama_scx_decode_begin_v1(const server_scx_event * event) {
    __asm__ __volatile__("nop" : : "r"(event) : "memory");
}

__attribute__((noinline, used, visibility("default")))
void llama_scx_decode_end_v1(const server_scx_event * event) {
    __asm__ __volatile__("nop; nop" : : "r"(event) : "memory");
}
}

class server_scx_state_sync {
    llama_context * ctx;
    bool active;
public:
    server_scx_state_sync(llama_context * ctx, bool active) : ctx(ctx), active(active) {
        if (active) { llama_synchronize(ctx); }
    }
    server_scx_state_sync(const server_scx_state_sync &) = delete;
    server_scx_state_sync & operator=(const server_scx_state_sync &) = delete;
    void finish() {
        if (active) {
            llama_synchronize(ctx);
            active = false;
        }
    }
    ~server_scx_state_sync() { finish(); }
};

class server_scx_scope {
    llama_context * ctx;
    server_scx_event event;
    bool active;
public:
    server_scx_scope(llama_context * ctx, server_scx_event event) : ctx(ctx), event(event), active(event.run_id != 0) {
        if (active) {
            llama_synchronize(ctx);
            llama_scx_decode_begin_v1(&this->event);
        }
    }
    server_scx_scope(const server_scx_scope &) = delete;
    server_scx_scope & operator=(const server_scx_scope &) = delete;
    void finish(int result) {
        if (active) {
            llama_synchronize(ctx);
            event.result = result;
            llama_scx_decode_end_v1(&event);
            active = false;
        }
    }
    ~server_scx_scope() { finish(-1); }
};
#endif
