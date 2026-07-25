// count: 1
struct Outer {
    /* +0 */ struct { int x; } inner;
};
// ---
struct Outer_inner { int x; };

struct Outer {
    /* +0 */ struct Outer_inner inner;
};
