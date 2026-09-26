/* flatland_core.h — contiguous native struct buffers for Phase M-4
 * Zero-copy, cache-line aligned, OpenMP-ready.
 */
#pragma once
#include <stdint.h>

#define CREATURE_STATE_ALIGN 64
#define SPATIAL_ENTITY_ALIGN 64
#define CREATURE_OUTPUT_ALIGN 64

/* 64/128 bytes, cache-line aligned */
typedef struct __attribute__((aligned(64))) {
    int32_t id;
    int32_t pad0;
    double x, y, angle, speed, energy, health, radius;
    int32_t caste;      /* 0..7 mapped from caste string */
    int32_t clan_id;
    int32_t flags;      /* bit0=is_predator bit1=indoors bit2=sleeping bit3=infected */
    int32_t pad1;
} CreatureStateC;

/* 64 bytes */
typedef struct __attribute__((aligned(64))) {
    int32_t id;
    int32_t kind;       /* 0=food 1=corpse 2=house 3=creature */
    int32_t variant;    /* food variant index */
    int32_t pad;
    double x, y, radius;
    double extra;        /* growth / hp etc */
} SpatialEntityC;

/* 64 bytes */
typedef struct __attribute__((aligned(64))) {
    double next_x, next_y, next_angle;
    double delta_energy, delta_health;
    int32_t target_eaten_id;   /* -1 if none */
    int32_t bitten_prey_id;    /* -1 if none */
    int32_t action_flags;      /* bit0=ate bit1=bitten bit2=fled */
    int32_t pad;
} CreatureOutputC;

/* Parallel batch kernel — implemented in flatland_core.c */
#ifdef __cplusplus
extern "C" {
#endif
int c_batch_update_creatures_omp(
    const CreatureStateC* in_creatures, int n_creatures,
    const SpatialEntityC* entities, int n_entities,
    const double* cell_heads, int n_cells, /* spatial hash cell start indices or NULL for brute */
    double width, double height, int is_wrap,
    double wind_cos, double wind_sin, double wind_speed,
    CreatureOutputC* out
);

void c_batch_query_radius_omp(
    const double* qx, const double* qy, const double* qradius, int num_queries,
    const double* entity_x, const double* entity_y, const int* entity_ids, int num_entities,
    double width, double height, int is_wrap,
    int max_per_query,
    int* out_counts, int* out_ids, double* out_dist_sq
);
#ifdef __cplusplus
}
#endif

