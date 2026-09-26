"""Native C acceleration bridge (AJ Phase 3 + AY Phase M-2) with pure Python fallback.

Provides compiled C99 speedups for spatial queries, vector math,
toroidal distance, raycasting and collision sweeps.
"""

import ctypes
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

_C_LIB = None  # type: ignore
_LIB_DIR = Path(__file__).resolve().parent
_SRC_PATH = _LIB_DIR / "flatland_core.c"
_HDR_PATH = _LIB_DIR / "flatland_core.h"
_LIB_PATH = _LIB_DIR / ("_flatland_core.dylib" if sys.platform == "darwin" else "_flatland_core.so")

# M-4 contiguous structs (64/64/64 bytes, cache-line aligned) — zero-copy
class CreatureStateC(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_int32),
        ("pad0", ctypes.c_int32),
        ("x", ctypes.c_double), ("y", ctypes.c_double), ("angle", ctypes.c_double),
        ("speed", ctypes.c_double), ("energy", ctypes.c_double), ("health", ctypes.c_double), ("radius", ctypes.c_double),
        ("caste", ctypes.c_int32), ("clan_id", ctypes.c_int32), ("flags", ctypes.c_int32), ("pad1", ctypes.c_int32),
    ]

class SpatialEntityC(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_int32), ("kind", ctypes.c_int32), ("variant", ctypes.c_int32), ("pad", ctypes.c_int32),
        ("x", ctypes.c_double), ("y", ctypes.c_double), ("radius", ctypes.c_double), ("extra", ctypes.c_double),
    ]

class CreatureOutputC(ctypes.Structure):
    _fields_ = [
        ("next_x", ctypes.c_double), ("next_y", ctypes.c_double), ("next_angle", ctypes.c_double),
        ("delta_energy", ctypes.c_double), ("delta_health", ctypes.c_double),
        ("target_eaten_id", ctypes.c_int32), ("bitten_prey_id", ctypes.c_int32), ("action_flags", ctypes.c_int32), ("pad", ctypes.c_int32),
    ]


def _compile_native_core() -> bool:
    """Attempt to compile flatland_core.c using clang or gcc if available.
    M-4: tries OpenMP + march native + no-fast-math, falls back to serial.
    """
    if not _SRC_PATH.exists():
        return False
    # also check header mtime
    hdr_mtime = _HDR_PATH.stat().st_mtime if _HDR_PATH.exists() else 0
    src_mtime = max(_SRC_PATH.stat().st_mtime, hdr_mtime)
    if _LIB_PATH.exists() and _LIB_PATH.stat().st_mtime >= src_mtime:
        return True
    cc = os.environ.get("CC", "clang" if sys.platform == "darwin" else "gcc")
    # M-4: try OpenMP parallel build first, fallback to serial (-fno-fast-math for exact float64 parity)
    base_cmd = [cc, "-O3", "-shared", "-fPIC", "-Wall", "-fno-fast-math", "-march=native", str(_SRC_PATH), "-o", str(_LIB_PATH), "-lm"]
    omp_cmd = [cc, "-O3", "-shared", "-fPIC", "-fopenmp", "-march=native", "-fno-fast-math", "-Wall", str(_SRC_PATH), "-o", str(_LIB_PATH), "-lm"]
    for cmd in (omp_cmd, base_cmd):
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=15)
            if res.returncode == 0 and _LIB_PATH.exists():
                return True
        except Exception:
            continue
    return False


def _init_native_lib():
    global _C_LIB
    if _C_LIB is not None:
        return _C_LIB
    try:
        if _compile_native_core():
            lib = ctypes.CDLL(str(_LIB_PATH))
            lib.c_query_radius.argtypes = [
                ctypes.c_double, ctypes.c_double, ctypes.c_double,
                ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_int), ctypes.c_int,
                ctypes.c_double, ctypes.c_double, ctypes.c_int,
                ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_double),
                ctypes.c_int,
            ]
            lib.c_query_radius.restype = ctypes.c_int

            lib.c_spatial_hash_query.argtypes = [
                ctypes.c_double, ctypes.c_double, ctypes.c_double,
                ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_int), ctypes.c_int,
                ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
                ctypes.c_int, ctypes.c_int, ctypes.c_double,
                ctypes.c_double, ctypes.c_double, ctypes.c_int,
                ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_double),
                ctypes.c_int,
            ]
            lib.c_spatial_hash_query.restype = ctypes.c_int

            lib.c_toroidal_dist_sq.argtypes = [
                ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                ctypes.c_double, ctypes.c_double, ctypes.c_int,
            ]
            lib.c_toroidal_dist_sq.restype = ctypes.c_double

            lib.c_segments_intersect.argtypes = [
                ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
            ]
            lib.c_segments_intersect.restype = ctypes.c_int

            lib.c_path_crosses_wall.argtypes = [
                ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
                ctypes.POINTER(ctypes.c_double), ctypes.c_int,
            ]
            lib.c_path_crosses_wall.restype = ctypes.c_int

            lib.c_boids_separation.argtypes = [
                ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_int), ctypes.c_int,
                ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_int,
                ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
            ]
            lib.c_boids_separation.restype = None

            lib.c_boids_alignment.argtypes = [
                ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_int), ctypes.c_int,
                ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_int,
                ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
            ]
            lib.c_boids_alignment.restype = None

            lib.c_boids_cohesion.argtypes = [
                ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_int), ctypes.c_int,
                ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_int,
                ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
            ]
            lib.c_boids_cohesion.restype = None

            lib.c_collision_sweep.argtypes = [
                ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
                ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_int), ctypes.c_int,
                ctypes.c_double, ctypes.c_double, ctypes.c_int,
                ctypes.POINTER(ctypes.c_int), ctypes.c_int,
            ]
            lib.c_collision_sweep.restype = ctypes.c_int

            try:
                lib.c_elev_at.argtypes = [
                    ctypes.c_double, ctypes.c_double,
                    ctypes.POINTER(ctypes.c_double), ctypes.c_int, ctypes.c_int,
                    ctypes.c_double, ctypes.c_double,
                ]
                lib.c_elev_at.restype = ctypes.c_double
            except Exception:
                pass

            # M-4 OpenMP batch kernel — releases GIL via ctypes
            try:
                lib.c_batch_update_creatures_omp.argtypes = [
                    ctypes.POINTER(CreatureStateC), ctypes.c_int,
                    ctypes.POINTER(SpatialEntityC), ctypes.c_int,
                    ctypes.POINTER(ctypes.c_double), ctypes.c_int,
                    ctypes.c_double, ctypes.c_double, ctypes.c_int,
                    ctypes.c_double, ctypes.c_double, ctypes.c_double,
                    ctypes.POINTER(CreatureOutputC),
                ]
                lib.c_batch_update_creatures_omp.restype = ctypes.c_int
            except Exception:
                pass

            try:
                lib.c_batch_query_radius_omp.argtypes = [
                    ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double), ctypes.c_int,
                    ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_int), ctypes.c_int,
                    ctypes.c_double, ctypes.c_double, ctypes.c_int,
                    ctypes.c_int,
                    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_double),
                ]
                lib.c_batch_query_radius_omp.restype = None
            except Exception:
                pass

            _C_LIB = lib
            return _C_LIB
    except Exception:
        _C_LIB = None
    return None


_init_native_lib()


def is_native_available() -> bool:
    return _C_LIB is not None


# ------------------------------------------------------------------ queries

def native_query_radius(
    qx: float, qy: float, radius: float,
    entity_x: Sequence[float], entity_y: Sequence[float], entity_ids: Sequence[int],
    width: float, height: float, is_wrap: bool,
    max_out: int = 1024,
) -> tuple[list[int], list[float]]:
    lib = _C_LIB
    n = len(entity_ids)
    if lib is None or n == 0:
        r2 = radius * radius
        half_w = width * 0.5
        half_h = height * 0.5
        out_ids: list[int] = []
        out_d2: list[float] = []
        for i in range(n):
            dx = abs(qx - entity_x[i])
            dy = abs(qy - entity_y[i])
            if is_wrap:
                if dx > half_w: dx -= width
                if dy > half_h: dy -= height
            d2 = dx * dx + dy * dy
            if d2 <= r2:
                out_ids.append(entity_ids[i])
                out_d2.append(d2)
                if len(out_ids) >= max_out: break
        return out_ids, out_d2
    c_x = (ctypes.c_double * n)(*entity_x)
    c_y = (ctypes.c_double * n)(*entity_y)
    c_ids = (ctypes.c_int * n)(*entity_ids)
    out_ids_buf = (ctypes.c_int * max_out)()
    out_d2_buf = (ctypes.c_double * max_out)()
    found = lib.c_query_radius(
        ctypes.c_double(qx), ctypes.c_double(qy), ctypes.c_double(radius),
        c_x, c_y, c_ids, ctypes.c_int(n),
        ctypes.c_double(width), ctypes.c_double(height), ctypes.c_int(1 if is_wrap else 0),
        out_ids_buf, out_d2_buf, ctypes.c_int(max_out),
    )
    return list(out_ids_buf[:found]), list(out_d2_buf[:found])


def native_toroidal_dist_sq(ax: float, ay: float, bx: float, by: float, width: float, height: float, is_wrap: bool) -> float:
    if _C_LIB is not None:
        return float(_C_LIB.c_toroidal_dist_sq(
            ctypes.c_double(ax), ctypes.c_double(ay), ctypes.c_double(bx), ctypes.c_double(by),
            ctypes.c_double(width), ctypes.c_double(height), ctypes.c_int(1 if is_wrap else 0)))
    # pure python
    dx = abs(ax - bx); dy = abs(ay - by)
    if is_wrap:
        hw = width * 0.5; hh = height * 0.5
        if dx > hw: dx -= width
        if dy > hh: dy -= height
    return dx * dx + dy * dy


def native_segments_intersect(p1, p2, q1, q2) -> bool:
    if _C_LIB is not None:
        return bool(_C_LIB.c_segments_intersect(
            ctypes.c_double(p1[0]), ctypes.c_double(p1[1]), ctypes.c_double(p2[0]), ctypes.c_double(p2[1]),
            ctypes.c_double(q1[0]), ctypes.c_double(q1[1]), ctypes.c_double(q2[0]), ctypes.c_double(q2[1])))
    # python fallback
    def _cross(ax, ay, bx, by): return ax * by - ay * bx
    rx, ry = p2[0] - p1[0], p2[1] - p1[1]
    sx, sy = q2[0] - q1[0], q2[1] - q1[1]
    denom = _cross(rx, ry, sx, sy)
    if abs(denom) < 1e-12: return False
    qpx, qpy = q1[0] - p1[0], q1[1] - p1[1]
    t = _cross(qpx, qpy, sx, sy) / denom
    u = _cross(qpx, qpy, rx, ry) / denom
    return 0 <= t <= 1 and 0 <= u <= 1


def native_path_crosses_wall(x0: float, y0: float, x1: float, y1: float, wall_segs: list[tuple[float,float,float,float]]) -> bool:
    if not wall_segs:
        return False
    if _C_LIB is not None:
        n = len(wall_segs)
        flat = (ctypes.c_double * (n * 4))(*[c for seg in wall_segs for c in seg])
        return bool(_C_LIB.c_path_crosses_wall(
            ctypes.c_double(x0), ctypes.c_double(y0), ctypes.c_double(x1), ctypes.c_double(y1),
            flat, ctypes.c_int(n)))
    # fallback
    for seg in wall_segs:
        if native_segments_intersect((x0,y0),(x1,y1),(seg[0],seg[1]),(seg[2],seg[3])):
            return True
    return False


def native_boids_forces(x: Sequence[float], y: Sequence[float], angles: Sequence[float], clan_ids: Sequence[int], radius: float, width: float, height: float, is_wrap: bool):
    """Return separation, alignment, cohesion vectors from native core (or python fallback)."""
    n = len(x)
    if n == 0:
        return [], [], [], [], [], []
    if _C_LIB is None:
        # pure python separation fallback (slow)
        sep_x = [0.0]*n; sep_y = [0.0]*n
        half_w = width*0.5; half_h = height*0.5
        r2 = radius*radius
        for i in range(n):
            fx = fy = 0.0
            for j in range(n):
                if i==j or clan_ids[j]!=clan_ids[i]: continue
                dx = x[i]-x[j]; dy = y[i]-y[j]
                if is_wrap:
                    if dx > half_w: dx -= width
                    elif dx < -half_w: dx += width
                    if dy > half_h: dy -= height
                    elif dy < -half_h: dy += height
                d2 = dx*dx+dy*dy
                if 0.0001 < d2 < r2:
                    inv = 1.0/d2
                    fx += dx*inv; fy += dy*inv
            sep_x[i]=fx; sep_y[i]=fy
        return sep_x, sep_y, [0.0]*n, [0.0]*n, [0.0]*n, [0.0]*n
    cx = (ctypes.c_double * n)(*x); cy = (ctypes.c_double * n)(*y)
    cang = (ctypes.c_double * n)(*angles); cclan = (ctypes.c_int * n)(*clan_ids)
    sep_x = (ctypes.c_double * n)(); sep_y = (ctypes.c_double * n)()
    ali_x = (ctypes.c_double * n)(); ali_y = (ctypes.c_double * n)()
    coh_x = (ctypes.c_double * n)(); coh_y = (ctypes.c_double * n)()
    _C_LIB.c_boids_separation(cx, cy, cclan, n, ctypes.c_double(radius*radius),
                              ctypes.c_double(width), ctypes.c_double(height), ctypes.c_int(1 if is_wrap else 0),
                              sep_x, sep_y)
    _C_LIB.c_boids_alignment(cx, cy, cang, cclan, n, ctypes.c_double(radius),
                             ctypes.c_double(width), ctypes.c_double(height), ctypes.c_int(1 if is_wrap else 0),
                             ali_x, ali_y)
    _C_LIB.c_boids_cohesion(cx, cy, cclan, n, ctypes.c_double(radius),
                            ctypes.c_double(width), ctypes.c_double(height), ctypes.c_int(1 if is_wrap else 0),
                            coh_x, coh_y)
    return list(sep_x), list(sep_y), list(ali_x), list(ali_y), list(coh_x), list(coh_y)


def native_collision_sweep(x: Sequence[float], y: Sequence[float], radius: Sequence[float], ids: Sequence[int], width: float, height: float, is_wrap: bool) -> list[tuple[int,int]]:
    n = len(ids)
    if n == 0 or _C_LIB is None:
        # python fallback
        out=[]
        hw=width*0.5; hh=height*0.5
        for i in range(n):
            for j in range(i+1,n):
                dx=abs(x[i]-x[j]); dy=abs(y[i]-y[j])
                if is_wrap:
                    if dx>hw: dx=width-dx
                    if dy>hh: dy=height-dy
                rr=radius[i]+radius[j]
                if dx*dx+dy*dy < rr*rr:
                    out.append((ids[i],ids[j]))
        return out
    cx=(ctypes.c_double*n)(*x); cy=(ctypes.c_double*n)(*y); cr=(ctypes.c_double*n)(*radius); cids=(ctypes.c_int*n)(*ids)
    max_pairs=n*2
    out_buf=(ctypes.c_int*(max_pairs*2))()
    cnt=_C_LIB.c_collision_sweep(cx,cy,cr,cids,n, ctypes.c_double(width), ctypes.c_double(height), ctypes.c_int(1 if is_wrap else 0), out_buf, ctypes.c_int(max_pairs*2))
    return [(int(out_buf[i*2]), int(out_buf[i*2+1])) for i in range(min(cnt, max_pairs))]


def native_batch_update(creatures, entities, width: float, height: float, is_wrap: bool, wind_cos: float = 0.0, wind_sin: float = 0.0, wind_speed: float = 0.0):
    """M-4: pack creatures/entities into contiguous C buffers, call OpenMP kernel (GIL released), return outputs.
    Falls back to python if native not available.
    """
    if _C_LIB is None or not hasattr(_C_LIB, "c_batch_update_creatures_omp"):
        return None
    n_c = len(creatures)
    n_e = len(entities)
    if n_c == 0:
        return []
    # pack
    c_buf = (CreatureStateC * n_c)()
    for i, c in enumerate(creatures):
        c_buf[i].id = int(c.id)
        c_buf[i].pad0 = 0
        c_buf[i].x = float(c.x); c_buf[i].y = float(c.y); c_buf[i].angle = float(getattr(c, "angle", 0.0))
        c_buf[i].speed = float(getattr(c, "speed", 0.6)); c_buf[i].energy = float(getattr(c, "energy", 80.0))
        c_buf[i].health = float(getattr(c, "health", 100.0)); c_buf[i].radius = float(getattr(c, "radius", 1.0))
        c_buf[i].caste = int({"Woman":0,"Soldier":1,"Artisan":2,"Gentleman":3,"Professional":4,"Noble":5,"Priest":6,"Predator":7,"Herbivore":8}.get(getattr(c, "caste","Soldier"),1))
        c_buf[i].clan_id = int(getattr(c, "clan_id",0) or 0)
        flags = 0
        if getattr(c, "is_predator", False): flags |= 1
        if getattr(c, "indoors", False): flags |= 2
        if getattr(c, "sleeping", False): flags |= 4
        if getattr(c, "infected", False): flags |= 8
        c_buf[i].flags = flags
        c_buf[i].pad1 = 0
    e_buf = (SpatialEntityC * max(1, n_e))()
    if n_e:
        for i, e in enumerate(entities):
            e_buf[i].id = int(e.id)
            kind = 0 if e.kind=="food" else 1 if e.kind=="corpse" else 2 if e.kind=="house" else 3
            e_buf[i].kind = kind
            e_buf[i].variant = 0
            e_buf[i].pad = 0
            e_buf[i].x = float(e.x); e_buf[i].y = float(e.y); e_buf[i].radius = float(getattr(e, "radius", 1.0))
            e_buf[i].extra = float(getattr(e, "growth", 0.0))
    out_buf = (CreatureOutputC * n_c)()
    # call — ctypes releases GIL, OpenMP runs on 4 cores
    try:
        n = _C_LIB.c_batch_update_creatures_omp(
            c_buf, ctypes.c_int(n_c),
            e_buf, ctypes.c_int(n_e),
            None, ctypes.c_int(0),
            ctypes.c_double(width), ctypes.c_double(height), ctypes.c_int(1 if is_wrap else 0),
            ctypes.c_double(wind_cos), ctypes.c_double(wind_sin), ctypes.c_double(wind_speed),
            out_buf,
        )
    except Exception:
        return None
    return [(int(out_buf[i].target_eaten_id), float(out_buf[i].next_x), float(out_buf[i].next_y), float(out_buf[i].next_angle), float(out_buf[i].delta_energy), float(out_buf[i].delta_health)) for i in range(n_c)]


def native_elev_at(x: float, y: float, grid_buf: Any, cols: int, rows: int, width: float, height: float) -> float:
    """Fast bilinear elevation query in compiled C."""
    if _C_LIB is not None and hasattr(_C_LIB, "c_elev_at"):
        return float(_C_LIB.c_elev_at(
            ctypes.c_double(x), ctypes.c_double(y),
            grid_buf, ctypes.c_int(cols), ctypes.c_int(rows),
            ctypes.c_double(width), ctypes.c_double(height)
        ))
    return 0.5


def native_batch_query_radius(
    query_x: Sequence[float], query_y: Sequence[float], query_r: Sequence[float],
    entity_x: Sequence[float], entity_y: Sequence[float], entity_ids: Sequence[int],
    width: float, height: float, is_wrap: bool,
    max_per_query: int = 128,
) -> list[tuple[list[int], list[float]]]:
    """Batch-vectorize spatial perception queries via ctypes OpenMP with GIL release."""
    n_q = len(query_x)
    n_e = len(entity_ids)
    if n_q == 0:
        return []
    if n_e == 0 or _C_LIB is None or not hasattr(_C_LIB, "c_batch_query_radius_omp"):
        return [
            native_query_radius(query_x[i], query_y[i], query_r[i], entity_x, entity_y, entity_ids, width, height, is_wrap, max_per_query)
            for i in range(n_q)
        ]
    cq_x = (ctypes.c_double * n_q)(*query_x)
    cq_y = (ctypes.c_double * n_q)(*query_y)
    cq_r = (ctypes.c_double * n_q)(*query_r)
    ce_x = (ctypes.c_double * n_e)(*entity_x)
    ce_y = (ctypes.c_double * n_e)(*entity_y)
    ce_ids = (ctypes.c_int * n_e)(*entity_ids)
    out_counts = (ctypes.c_int * n_q)()
    total_buf = n_q * max_per_query
    out_ids = (ctypes.c_int * total_buf)()
    out_d2 = (ctypes.c_double * total_buf)()
    _C_LIB.c_batch_query_radius_omp(
        cq_x, cq_y, cq_r, ctypes.c_int(n_q),
        ce_x, ce_y, ce_ids, ctypes.c_int(n_e),
        ctypes.c_double(width), ctypes.c_double(height), ctypes.c_int(1 if is_wrap else 0),
        ctypes.c_int(max_per_query),
        out_counts, out_ids, out_d2,
    )
    res = []
    for q in range(n_q):
        cnt = min(int(out_counts[q]), max_per_query)
        base = q * max_per_query
        res.append((list(out_ids[base : base + cnt]), list(out_d2[base : base + cnt])))
    return res


