// count: 0
// remaining-violations: 2, 4
struct Outer {
    union {
        int x;
        struct { int y; };
    };
};
// ---
struct Outer {
    union {
        int x;
        struct { int y; };
    };
};
