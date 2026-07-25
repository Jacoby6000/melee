// count: 1
struct Outer {
    struct { int x; } a, b;
};
// ---
struct Outer_b { int x; };

struct Outer {
    struct Outer_b a, b;
};
