#ifndef RUNTIME_PLATFORM_H
#define RUNTIME_PLATFORM_H

#include <stdbool.h>       // IWYU pragma: export
#include <stddef.h>        // IWYU pragma: export
#include <dolphin/types.h> // IWYU pragma: export

/// The underlying type of an @c enum, used as a placeholder
typedef int enum_t;

/// A @c void callback with no arguments.
typedef void (*Event)(void);

#if defined(__MWERKS__) && defined(__PPCGEKKO__)
#define MWERKS_GEKKO
#endif

#ifndef ATTRIBUTE_ALIGN
#if defined(__MWERKS__) || defined(__GNUC__)
#define ATTRIBUTE_ALIGN(num) __attribute__((aligned(num)))
#elif defined(_MSC_VER)
#define ATTRIBUTE_ALIGN(num)
#else
#error unknown compiler
#endif
#endif

#ifndef SECTION_INIT
#if defined(__MWERKS__) && !defined(M2CTX)
#define SECTION_INIT __declspec(section ".init")
#else
#define SECTION_INIT
#endif
#endif

#ifndef SECTION_CTORS
#if defined(__MWERKS__) && !defined(M2CTX)
#define SECTION_CTORS __declspec(section ".ctors")
#else
#define SECTION_CTORS
#endif
#endif

#ifndef SECTION_DTORS
#if defined(__MWERKS__) && !defined(M2CTX)
#define SECTION_DTORS __declspec(section ".dtors")
#else
#define SECTION_DTORS
#endif
#endif

#ifndef ATTRIBUTE_NORETURN
#if defined(__clang__) || defined(__GNUC__)
#define ATTRIBUTE_NORETURN __attribute__((noreturn))
#else
#define ATTRIBUTE_NORETURN
#endif
#endif

#ifndef ATTRIBUTE_RESTRICT
#if defined(__MWERKS__) && !defined(M2CTX)
#define ATTRIBUTE_RESTRICT __restrict
#else
#define ATTRIBUTE_RESTRICT
#endif
#endif

#ifdef PERMUTER
#define AT_ADDRESS(x) = FIXEDADDR(x)
#elif defined(__MWERKS__) && !defined(M2CTX)
#define AT_ADDRESS(x) : (x)
#else
#define AT_ADDRESS(x)
#endif

#ifdef __PPCGEKKO__
#define qr0 0
#define qr1 1
#define qr2 2
#define qr3 3
#define qr4 4
#define qr5 5
#define qr6 6
#define qr7 7
#endif

#define U8_MAX 0xFF
#define U16_MAX 0xFFFF
#define U32_MAX 0xFFFFFFFF
#define S8_MAX 0x7F
#define S16_MAX 0x7FFF
#define S32_MAX 0x7FFFFFFF
#define F32_MAX 3.4028235e38f

#define SQ(x) ((x) * (x))
#define MIN(a, b) (((a) < (b)) ? (a) : (b))
#define MAX(a, b) (((a) > (b)) ? (a) : (b))

#ifdef __cplusplus
#ifndef _Static_assert
#define _Static_assert static_assert
#endif
#endif
#ifdef M2CTX
#define STATIC_ASSERT(cond)
#elif defined(__MWERKS__)
#define STATIC_ASSERT(cond)                                                   \
    struct {                                                                  \
        int x[1 - 2 * !(cond)];                                               \
    };
#else
#define STATIC_ASSERT(cond) _Static_assert((cond), "(" #cond ") failed")
#endif

#define STATIC_ASSERT_CONCAT_(a, b) a##b
#define STATIC_ASSERT_CONCAT(a, b) STATIC_ASSERT_CONCAT_(a, b)

// STATIC_ASSERT_SIZE(type, size) fails to compile unless sizeof(type) == size,
// and (unlike STATIC_ASSERT) reports both the actual and expected sizes.
//
// DESNOTE(jbarber, 2026-07-07): The two array typedefs share a name, so a size
// mismatch surfaces as a redeclaration diagnostic that prints both the actual
// (sizeof) and expected bounds: mwcc reports "was declared as 'char[96]'" /
// "now declared as 'char[104]'", while clang/gcc report "'char[104]' vs
// 'char[96]'". A plain STATIC_ASSERT collapses the comparison to a bool before
// the compiler sees it, so both numbers are lost. The typedef name is keyed on
// __LINE__ and the expected size so two correct asserts can never produce a
// false conflict (matching sizes yield an identical, legal typedef
// redefinition); `size` must therefore be an integer literal, and sizes are
// printed in decimal.
//
// The matching case relies on identical typedef redefinition, which is a C11
// feature, so clang warns -Wtypedef-redefinition on every correct assert when
// tooling (clangd/CI) builds in a pre-C11 mode. We silence just that warning
// on clang; the mismatch remains a separate, unconditional "different types"
// error that still prints both sizes. gcc and mwcc accept the redefinition
// without a warning under the flags we build with, so they need no pragma.
#ifdef M2CTX
#define STATIC_ASSERT_SIZE(type, size)
#elif defined(__clang__)
#define STATIC_ASSERT_SIZE(type, size)                                        \
    _Pragma("clang diagnostic push") _Pragma(                                 \
        "clang diagnostic ignored \"-Wtypedef-redefinition\"") typedef char   \
        STATIC_ASSERT_CONCAT(                                                 \
            STATIC_ASSERT_CONCAT(static_assert_size_at_line_, __LINE__),      \
            STATIC_ASSERT_CONCAT(_expected_, size))[(int) (size)];            \
    typedef char STATIC_ASSERT_CONCAT(                                        \
        STATIC_ASSERT_CONCAT(static_assert_size_at_line_, __LINE__),          \
        STATIC_ASSERT_CONCAT(_expected_, size))[(int) sizeof(type)];          \
    _Pragma("clang diagnostic pop")
#else
#define STATIC_ASSERT_SIZE(type, size)                                        \
    typedef char STATIC_ASSERT_CONCAT(                                        \
        STATIC_ASSERT_CONCAT(static_assert_size_at_line_, __LINE__),          \
        STATIC_ASSERT_CONCAT(_expected_, size))[(int) (size)];                \
    typedef char STATIC_ASSERT_CONCAT(                                        \
        STATIC_ASSERT_CONCAT(static_assert_size_at_line_, __LINE__),          \
        STATIC_ASSERT_CONCAT(_expected_, size))[(int) sizeof(type)]
#endif

#define RETURN_IF(cond)                                                       \
    do {                                                                      \
        if ((cond)) {                                                         \
            return;                                                           \
        }                                                                     \
    } while (0)

#if defined(__MWERKS__) && !defined(M2CTX)
#define SDATA __declspec(section ".sdata")
#define DATA __declspec(section ".data")
#define WEAK __declspec(weak)
#else
#define SDATA
#define DATA
#define WEAK
#endif

#endif
