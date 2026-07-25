// violations: 2
struct Outer {
    union Bar {
        int x;
        float y;
    } u;
};
