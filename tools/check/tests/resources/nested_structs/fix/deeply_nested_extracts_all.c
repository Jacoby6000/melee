// count: 2
struct A {
    struct B {
        struct C {
            int z;
        } deep;
    } inner;
};
// ---
struct C {
    int z;
};

struct B {
    struct C deep;
};

struct A {
    struct B inner;
};
