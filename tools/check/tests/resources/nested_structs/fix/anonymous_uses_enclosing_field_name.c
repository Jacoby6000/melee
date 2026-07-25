// count: 1
struct Outer {
    struct {
        int x;
    } bar_field;
};
// ---
struct Outer_bar_field {
    int x;
};

struct Outer {
    struct Outer_bar_field bar_field;
};
