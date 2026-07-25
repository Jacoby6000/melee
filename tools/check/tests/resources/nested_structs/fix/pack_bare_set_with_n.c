// count: 1
#pragma pack(4)
struct Outer {
    struct Foo {
        int x;
    } inner;
};
#pragma pack()
// ---
#pragma pack(4)
struct Foo {
    int x;
};

struct Outer {
    struct Foo inner;
};
#pragma pack()
