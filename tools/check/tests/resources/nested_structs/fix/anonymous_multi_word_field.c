// count: 1
union V {
    struct { int x; } some_name;
};
// ---
struct V_some_name { int x; };

union V {
    struct V_some_name some_name;
};
