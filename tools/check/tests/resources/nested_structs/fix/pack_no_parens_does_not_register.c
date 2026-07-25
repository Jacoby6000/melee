// count: 1
#pragma pack
struct Outer {
    struct Foo {
        int x;
    } inner;
};
#pragma pack()
// ---
#pragma pack
struct Foo {
    int x;
};

struct Outer {
    struct Foo inner;
};
#pragma pack()
