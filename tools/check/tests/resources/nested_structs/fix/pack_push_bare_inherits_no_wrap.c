// count: 1
#pragma pack(push)
struct Outer {
    struct Foo {
        int x;
    } inner;
};
#pragma pack(pop)
// ---
#pragma pack(push)
struct Foo {
    int x;
};

struct Outer {
    struct Foo inner;
};
#pragma pack(pop)
