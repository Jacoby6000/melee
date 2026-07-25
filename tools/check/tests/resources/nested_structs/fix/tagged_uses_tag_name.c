// count: 1
struct Outer {
    struct Foo {
        int x;
    } inner;
};
// ---
struct Foo {
    int x;
};

struct Outer {
    struct Foo inner;
};
