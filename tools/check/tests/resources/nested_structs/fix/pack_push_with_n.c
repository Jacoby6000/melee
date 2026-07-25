// count: 1
#pragma pack(push, 1)
struct Outer {
    struct Foo {
        int x;
    } inner;
};
#pragma pack(pop)
// ---
#pragma pack(push, 1)
struct Foo {
    int x;
};

struct Outer {
    struct Foo inner;
};
#pragma pack(pop)
