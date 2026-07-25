// count: 1
#define LONG \
  VALUE
struct Outer {
    struct Foo {
        int x;
    } inner;
};
// ---
#define LONG \
  VALUE
struct Foo {
    int x;
};

struct Outer {
    struct Foo inner;
};
