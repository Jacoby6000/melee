// count: 1
#pragma pack(push, 2)
struct Outer {
    struct {
        int x;
    } bar_field;
};
#pragma pack(pop)
// ---
#pragma pack(push, 2)
struct Outer_bar_field {
    int x;
};

struct Outer {
    struct Outer_bar_field bar_field;
};
#pragma pack(pop)
