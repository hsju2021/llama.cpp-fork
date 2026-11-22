#include "../tools/server/server-scx.h"

#include <cstdio>
#include <cstdlib>

#define CHECK(condition) do { if (!(condition)) { std::fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #condition); std::abort(); } } while (0)

static int synchronizations = 0;
extern "C" void llama_synchronize(llama_context *) { ++synchronizations; }

int main() {
    server_scx_state_publisher publisher;
    int publications = 0;
    auto emit = [&](const server_scx_state_v2 *) { ++publications; };
    for (int i = 0; i < 2; ++i) {
        server_scx_state_sync sync(nullptr, true);
        publisher.publish(42, 2, true, emit);
        CHECK(synchronizations == 2 * i + 1);
        sync.finish();
        sync.finish();
        CHECK(synchronizations == 2 * i + 2);
    }
    CHECK(publications == 1 && synchronizations == 4);
    {
        server_scx_state_sync sync(nullptr, false);
        sync.finish();
    }
    CHECK(synchronizations == 4);
    try {
        server_scx_state_sync sync(nullptr, true);
        throw 1;
    } catch (int) {}
    CHECK(synchronizations == 6);

    server_scx_event event { 1, 42, 1, 0, 2, 0, 0, 1, 0, -1 };
    {
        server_scx_scope scope(nullptr, event);
        CHECK(synchronizations == 7);
        scope.finish(0);
        scope.finish(0);
    }
    CHECK(synchronizations == 8);
    try {
        server_scx_scope scope(nullptr, event);
        throw 1;
    } catch (int) {}
    CHECK(synchronizations == 10);
    event.run_id = 0;
    {
        server_scx_scope scope(nullptr, event);
        scope.finish(0);
    }
    CHECK(synchronizations == 10);
    std::puts("SCX synchronization: duplicate state, off, finish and exception paths passed");
}
