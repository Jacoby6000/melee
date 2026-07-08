#include "gr/forward.h"
#include "mn/forward.h"

#include "mn/mnevent.h"

#include <melee/gm/types.h>
#include <melee/mn/types.h>

struct UnkSmallLoadData {
    u8 pad[8];
};

typedef struct EventStageList {
    /* 0x00 */ u8 count;
    /* 0x01 */ u8 x1;
    /* 0x02 */ u16 stage[7];
    /* 0x10 */ EventCharacterInitData* player_init[5];
} EventStageList;

typedef struct BonusStyleEventInitCharacterData {
    /* 0x00 */ s8 c_kind;
    /* 0x01 */ u8 x1;
    /* 0x02 */ u8 x2;
    /* 0x03 */ u8 x3;
    /* 0x04 */ u8 x4;
    /* 0x05 */ u8 x5;
    /* 0x06 */ u8 color;
    /* 0x07 */ u8 pad7;
    /* 0x08 */ f32 x8;
    /* 0x0C */ f32 xC;
    /* 0x10 */ f32 x10;
    /* 0x14 */ u8 flags;
    /* 0x15 */ u8 x15;
    /* 0x16 */ u8 x16;
    /* 0x17 */ u8 x17;
} BonusStyleEventInitCharacterData;

typedef struct StartEventRules { ///< Largely mirrors StartMeleeRules in the
                                 ///< first couple of bytes, namely the bit
                                 /// flags.  When an event match is set up, a
                                 /// lot of this is copied in to
                                 /// StartMeleeRules
    u8 x0_0 : 1;
    u8 x0_1 : 1;
    u8 x0_2 : 1;
    u8 x0_3 : 1;
    u8 x0_4 : 1;
    u8 x0_5 : 1;
    u8 x0_6 : 1;
    u8 x0_7 : 1;
    u8 x1_0 : 1;
    u8 x1_1 : 1;
    u8 x1_2 : 1;
    u8 x1_3 : 1;
    u8 x1_4 : 1;
    u8 x1_5 : 1;
    u8 x1_6 : 1;
    u8 x1_7 : 1;
    u8 is_teams : 1;
    u8 x2_1 : 1;
    u8 x2_2 : 1;
    u8 x2_3 : 1;
    u8 x2_4 : 1;
    u8 x2_5 : 1;
    u8 x2_6 : 1;
    u8 x2_7 : 1;
    s8 x3; // iten frequency?
    s8 x4; // SD Penalty?
    u8 x5;
    u16 x6; // InternalStageId?
    u32 x8; // Time Limit?
    u8 padC[4];
    u64 x10; // Item Mask?
    s32 x18;
    f32 x1C;
    f32 x20;
    f32 x24;
} StartEventRules;

struct EventInitDataLevelTbl {
    /* 0x00 */ u8 kind; ///< 0: Standard, 1: Bonus, 2: Multi
    /* 0x01 */ u8 flags;
    /* 0x02 */ u8 pad2[2];
    /* 0x04 */ struct gm_804D6900_x4_t {
        int x0;
        EventCharacterInitData* x4;
    }* x4;
    /* 0x08 */ StartEventRules* x8;
    /* 0x0C */ struct BonusStyleEventInitCharacterData* xC;
    /* 0x10 */ EventStageList* stage_list;
    /* 0x14 */ EventCharacterInitData* player_init[5];
};

// The DOL has a single 8-byte object at
// 0x4D6900 (two pointer slots). Only slot [0] is ever used (as the loaded
// EventInitDataLevelTbl** base); slot [1] is reserved. Declaring it as a
// 2-element array reproduces the single 8-byte symbol so .sbss matches,
// instead of splitting it into a 4-byte pointer plus a 4-byte pad.
/* 4D6900 */ static struct EventInitDataLevelTbl**
    event_init_data_level_table[2];
/* 4D6908 */ static struct UnkSmallLoadData gm_804D6908;
/* 4D6910 */ static struct UnkSmallLoadData gm_804D6910;
/* 4D6918 */ static struct UnkSmallLoadData gm_804D6918;
/* 4D6920 */ static struct UnkSmallLoadData gm_804D6920;
/* 4D6928 */ static UNK_T gm_804D6928;
/* 4D692C */ static UNK_T gm_804D692C;
/* 4D6930 */ static struct UnkSmallLoadData gm_804D6930;
/* 4D6938 */ static UNK_T gm_804D6938;
/* 4D693C */ static UNK_T gm_804D693C;

/* 497758 */ static CSSData gm_80497758;
/* 4978A0 */ static StartMeleeData gm_804978A0;
/* 4979D8 */ static MatchExitInfo gm_804979D8[2];
/* 49BEE8 */ static CSSData gm_8049BEE8;
/* 49C030 */ static CSSData gm_8049C030;
/* 49C178 */ static u8 gm_8049C178[16];
/* 49C188 */ static UNK_T gm_8049C188[0x138 / 4];
/* 49C2C0 */ static MatchExitInfo gm_8049C2C0;
/* 49E548 */ static struct gm_8049E548_t gm_8049E548;
