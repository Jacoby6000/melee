// violations:
// checks:disable nested-structs
union V {
    struct { int x; } common;
    struct { int y; } walk;
};
// checks:enable
