// count: 1
#include <a.h>
#include <b.h>
#define X 1
struct Outer {
    struct Foo {
        int x;
    } inner;
};
// ---
#include <a.h>
#include <b.h>
#define X 1
struct Foo {
    int x;
};

struct Outer {
    struct Foo inner;
};
