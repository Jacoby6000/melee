// count: 2
union V {
    struct { int x; } common;
    struct { int y; } walk;
};
// ---
struct V_common { int x; };

struct V_walk { int y; };

union V {
    struct V_common common;
    struct V_walk walk;
};
