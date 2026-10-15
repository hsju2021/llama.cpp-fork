#include "../tools/server/server-scx.h"

#include <cstdio>
#include <cstdlib>
#include <vector>

#define CHECK(condition) do { if (!(condition)) { std::fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #condition); std::abort(); } } while (0)

struct recorder {
    server_scx_state_publisher publisher;
    std::vector<server_scx_state_v2> events;

    bool publish(uint32_t phase) {
        return publisher.publish(42, phase, true, [this](const server_scx_state_v2 * event) { events.push_back(*event); });
    }
    bool reconcile(bool processing) {
        return publisher.reconcile(42, processing, [this](const server_scx_state_v2 * event) { events.push_back(*event); });
    }
    void check() const {
        uint64_t sequence = 0;
        for (const auto & event : events) {
            CHECK(event.version == 2 && event.run_id == 42 && event.reserved == 0);
            CHECK(event.sequence == ++sequence);
            CHECK(event.active <= 1 && event.phase <= 3);
            CHECK(event.active || event.phase == 0);
        }
    }
};

static void test_lifecycle() {
    recorder r;
    bool processing = true;
    int settled = 0;
    auto reconcile = [&]() { r.reconcile(processing); };
    auto clear = [&]() { ++settled; r.reconcile(false); };
    r.publish(2);
    {
        server_scx_reconcile_scope guard(reconcile, clear);
        CHECK(r.events.size() == 1);
    }
    CHECK(r.events.size() == 1);
    {
        server_scx_reconcile_scope guard(reconcile, clear);
        processing = false;
    }
    CHECK(r.events.size() == 2);
    r.publish(2);
    processing = true;
    try {
        server_scx_reconcile_scope guard(reconcile, clear);
        throw 1;
    } catch (int) {}
    CHECK(settled == 1 && r.events.size() == 4 && r.events.back().active == 0);
    r.publish(1);
    clear();
    CHECK(r.events.size() == 6);
    r.publish(2);
    CHECK(r.events.back().sequence == 7);
    clear();
    CHECK(r.events.size() == 8);
    r.check();
}

static void test_early_return() {
    recorder r;
    r.publish(2);
    auto iteration = [&]() {
        server_scx_reconcile_scope guard([&]() { r.reconcile(false); }, [&]() { std::abort(); });
        return;
    };
    iteration();
    CHECK(r.events.size() == 2 && r.events.back().active == 0);
    r.check();
}

static void test_ranges() {
    recorder r;
    CHECK(server_scx_classify_phase(0, 0, 0) == 0);
    CHECK(server_scx_classify_phase(4, 3, 1) == 0);
    CHECK(server_scx_classify_phase(4, 0, 0) == 1);
    CHECK(server_scx_classify_phase(0, 3, 0) == 2);
    CHECK(server_scx_classify_phase(4, 3, 0) == 3);
    r.publish(server_scx_classify_phase(4, 3, 0));
    r.publish(server_scx_classify_phase(4, 0, 0));
    CHECK(!r.publish(server_scx_classify_phase(2, 0, 0)));
    r.publish(server_scx_classify_phase(0, 3, 0));
    r.reconcile(false);
    CHECK(r.events.size() == 4);
    r.check();
}

int main() {
    test_lifecycle();
    test_ranges();
    test_early_return();
    static_assert(offsetof(server_scx_event, version) == 0, "v1 version");
    static_assert(offsetof(server_scx_event, run_id) == 8, "v1 run_id");
    static_assert(offsetof(server_scx_event, call_id) == 16, "v1 call_id");
    static_assert(offsetof(server_scx_event, retry) == 24, "v1 retry");
    static_assert(offsetof(server_scx_event, phase) == 32, "v1 phase");
    static_assert(offsetof(server_scx_event, profile) == 40, "v1 profile");
    static_assert(offsetof(server_scx_event, n_prefill) == 48, "v1 n_prefill");
    static_assert(offsetof(server_scx_event, n_decode) == 56, "v1 n_decode");
    static_assert(offsetof(server_scx_event, n_unknown) == 64, "v1 n_unknown");
    static_assert(offsetof(server_scx_event, result) == 72, "v1 result");
    recorder repeated;
    CHECK(!repeated.reconcile(false));
    for (int i = 0; i < 100; ++i) {
        CHECK(repeated.publish(2) == (i == 0));
        CHECK(!repeated.reconcile(true));
    }
    CHECK(repeated.reconcile(false));
    CHECK(repeated.events.size() == 2);
    CHECK(repeated.events[0].phase == 2 && repeated.events[0].active == 1);
    CHECK(repeated.events[1].phase == 0 && repeated.events[1].active == 0);
    repeated.check();

    recorder transitions;
    for (uint32_t phase : { 1u, 2u, 2u, 3u, 2u }) { transitions.publish(phase); }
    transitions.reconcile(false);
    CHECK(transitions.events.size() == 5);
    transitions.check();

    recorder lifecycle;
    CHECK(lifecycle.publish(0));
    CHECK(lifecycle.events.back().active == 1 && lifecycle.events.back().phase == 0);
    CHECK(!lifecycle.reconcile(true));
    CHECK(lifecycle.reconcile(false));
    CHECK(!lifecycle.reconcile(false));
    CHECK(lifecycle.publish(2));
    CHECK(lifecycle.reconcile(false));
    CHECK(lifecycle.publish(1));
    CHECK(lifecycle.events.back().sequence == 5);
    CHECK(lifecycle.reconcile(false));
    lifecycle.check();

    server_scx_state_publisher disabled;
    CHECK(!disabled.publish(0, 2, true, [](const server_scx_state_v2 *) { std::abort(); }));
    int pinned_events = 0;
    auto pinned_emit = [&](const server_scx_state_v2 * event) {
        CHECK(event->run_id == 42 && event->sequence == uint64_t(++pinned_events));
    };
    server_scx_state_publisher pinned;
    CHECK(pinned.publish(42, 2, true, pinned_emit));
    CHECK(!pinned.publish(43, 1, true, pinned_emit));
    CHECK(!pinned.idle(43, pinned_emit));
    CHECK(pinned.idle(42, pinned_emit));
    CHECK(pinned_events == 2);
    std::puts("SCX state publisher: counts, active UNKNOWN, reconciliation, resume sequence and ABI passed");
}
