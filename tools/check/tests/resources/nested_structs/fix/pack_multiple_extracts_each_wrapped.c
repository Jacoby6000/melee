// count: 2
#pragma pack(push, 1)
struct Outer {
    struct Foo {
        int x;
    } a;
    struct Bar {
        int y;
    } b;
};
#pragma pack(pop)
// ---
#pragma pack(push, 1)
struct Foo {
    int x;
};

struct Bar {
    int y;
};

struct Outer {
    struct Foo a;
    struct Bar b;
};
#pragma pack(pop)
