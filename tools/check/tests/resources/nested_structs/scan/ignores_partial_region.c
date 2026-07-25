// violations: 5
// checks:disable nested-structs
union V {
    struct { int x; } common;
// checks:enable
    struct { int y; } walk;
};
