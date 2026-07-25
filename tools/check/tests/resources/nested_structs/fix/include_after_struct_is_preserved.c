// count: 1
struct Outer {
    struct Foo {
        int x;
    } inner;
};
#include <foo.h>
// ---
struct Foo {
    int x;
};

struct Outer {
    struct Foo inner;
};
#include <foo.h>
