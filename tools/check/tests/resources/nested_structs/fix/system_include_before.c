// count: 1
#include <foo.h>
struct Outer {
    struct Foo {
        int x;
    } inner;
};
// ---
#include <foo.h>
struct Foo {
    int x;
};

struct Outer {
    struct Foo inner;
};
