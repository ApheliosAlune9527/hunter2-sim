"""Clearance-checked Reeds–Shepp docking and stopped direction changes."""

import math

import numpy as np

from clearance import FOOTPRINT, angle


PLAN_GAP = 0.13
BRAKE_GAP = 0.07
# The evaluated stand-off is measured to the true face, while the dock is placed
# from the RGB-D face estimate, which sits 0.055 m towards the camera on this
# viewpoint, and the controller stops ~0.06-0.11 m behind its goal.  With 0.35
# the measured stand-off reached 0.509 m against a 0.50 m ceiling (run
# 20261110_055500); 0.28 leaves margin on both sides of the 0.23-0.50 window.
STANDOFF = 0.28
# The room's north wall leaves ~0.22 m between the docked body and the wall when
# the standoff point sits on the face centre line.  The 1.2 rad final turn then
# has only 0.185 m of planned clearance, and the controller's corner cutting
# (~0.10 m, 0.2 rad) drops the executed clearance to 0.067 m, under BRAKE_GAP.
# Shifting the standoff along the face tangent, away from that wall, buys the
# margin back; the box itself is not touched.
# Measured trade-off on 2026-11-10 (same scene, same instruction):
#   shift 0.00 -> parking leg canceled at 0.067 m clearance (below BRAKE_GAP)
#   shift 0.02 -> canceled at 0.068 m (a different, single-leg parking candidate)
#   shift 0.10 -> all five legs status 4 and stopped, wall clearance 0.218-0.356 m,
#                 but lateral offset from the true face centre 0.162 m (limit 0.11)
# The lateral check and the wall clearance pull in opposite directions here: the
# face-centre estimate itself is 0.03-0.07 m off towards the camera, so a shift
# above ~0.04 m cannot stay inside the 0.11 m lateral tolerance.  0.10 keeps the
# manoeuvre executable; passing the lateral check as well needs either a better
# face-centre estimate or a wider lateral tolerance.
DOCK_SIDE_SHIFT = 0.10
MIN_EXECUTABLE_REVERSE = 0.50
ENTRY_DISTANCES = (1.425, 1.225, 1.025, 0.825, 0.625)


def axes(yaw):
    along = np.array([math.cos(yaw), math.sin(yaw)])
    return along, np.array([-along[1], along[0]])


def dock_from_face(face):
    along, side = axes(face["heading"])
    point = np.asarray(face["centre"]) - along * (FOOTPRINT[:, 0].max() + STANDOFF)
    # side = (-sin, cos) is the left of the face normal; the north wall is on
    # that side in this scene, so shift towards -side.
    point = point - side * DOCK_SIDE_SHIFT
    return np.r_[point, face["heading"]]


def direction_parts(path):
    delta = np.diff(path, axis=0)
    distance = np.linalg.norm(delta[:, :2], axis=1)
    forward = np.column_stack((np.cos(path[:-1, 2]), np.sin(path[:-1, 2])))
    signs = np.sign(np.sum(delta[:, :2] * forward, axis=1)).astype(int)
    if not len(signs) or not np.all(signs):
        raise ValueError("path has a stationary segment")
    splits = [0, *(np.flatnonzero(np.diff(signs)) + 1), len(path) - 1]
    return [(int(signs[first]), path[first:last + 1], float(distance[first:last].sum()))
            for first, last in zip(splits, splits[1:])]


def backing_arc(start, distance, curvature):
    travel = np.linspace(0., -distance, math.ceil(distance / .04) + 1)
    x, y, yaw = start
    theta = yaw + curvature * travel
    if curvature:
        x = x + (np.sin(theta) - math.sin(yaw)) / curvature
        y = y + (math.cos(yaw) - np.cos(theta)) / curvature
    else:
        x = x + travel * math.cos(yaw)
        y = y + travel * math.sin(yaw)
    return np.column_stack((x, y, theta))


def straight_segment(start, dock):
    """Extend the current heading to the dock plane, with no lateral jump."""
    along, side = axes(dock[2])
    heading, _ = axes(start[2])
    remaining = float((dock[:2] - start[:2]) @ along)
    if remaining < .30 or abs(angle(start[2] - dock[2])) > .085:
        return None
    travel = remaining / float(heading @ along)
    finish = start[:2] + travel * heading
    if abs(float((finish - dock[:2]) @ side)) > .085:
        return None
    distance = np.linspace(0., travel, math.ceil(travel / .04) + 1)
    return np.column_stack((start[:2] + distance[:, None] * heading,
                            np.full(len(distance), start[2])))


def straight_finish(node, start, dock):
    along, side = axes(dock[2])
    delta = dock[:2] - start[:2]
    if not .30 <= delta @ along <= 1.55 or abs(delta @ side) > .085:
        return None, None
    path = straight_segment(start, dock)
    if path is None:
        return None, None
    audit = node.scene.sweep(path)
    if audit["clearance_m"] < PLAN_GAP:
        return None, None
    return path, dict(method="straight_finish", directions=[1],
                      length_m=math.dist(path[0, :2], path[-1, :2]), audit=audit)


def docking_path(node, start, dock, prefix=None, first_gear=None, *, forward=False):
    best = None
    plan_start = start if prefix is None else prefix[-1]
    along, side = axes(dock[2])
    for distance in ENTRY_DISTANCES:
        entry = np.r_[dock[:2] - distance * along, dock[2]]
        path = node.compute_plan(forward, plan_start, entry)
        if path is None or math.dist(path[-1, :2], entry[:2]) > .055:
            continue
        if abs(float((path[-1, :2] - dock[:2]) @ side)) > .05:
            continue
        tail = straight_segment(path[-1], dock)
        if tail is None:
            continue
        path = np.vstack((path, tail[1:]))
        if prefix is not None:
            path = np.vstack((prefix, path[1:]))
        parts = direction_parts(path)
        gears = [gear for gear, _, _ in parts]
        if (gears[-1] != 1 or any(length < .22 for _, _, length in parts)
                or (gears[0] == -1 and parts[0][2] < MIN_EXECUTABLE_REVERSE)
                or (first_gear is not None and gears[0] != first_gear)
                or (forward and gears != [1])):
            continue
        audit = node.scene.sweep([start, *path])
        length = sum(length for _, _, length in parts)
        gap = audit["clearance_m"]
        score = (gap >= PLAN_GAP, gap - .025 * length - .025 * (len(parts) - 1))
        info = dict(entry=entry.tolist(), audit=audit, length_m=length, directions=gears,
                    straight_m=math.dist(tail[0, :2], tail[-1, :2]))
        if best is None or score > best[0]:
            best = score, path, info
    return (best[1], best[2]) if best else (None, None)


def backout_path(node, start, dock):
    for distance in (.52, .80, 1.1):
        for curvature in (0., .45, -.45):
            prefix = backing_arc(start, distance, curvature)
            if node.scene.sweep(prefix)["clearance_m"] < PLAN_GAP:
                continue
            path, info = docking_path(node, start, dock, prefix=prefix, first_gear=-1)
            if info and info["audit"]["clearance_m"] >= PLAN_GAP:
                return path, info
    return None, None


def find_parking_path(node, start, dock, first_gear=None):
    _, side = axes(dock[2])
    for offset in (0., -.035, -.065):
        lane = dock.copy()
        lane[:2] += offset * side
        path, info = docking_path(node, start, lane, first_gear=first_gear)
        if info and info["audit"]["clearance_m"] >= PLAN_GAP:
            return path, info
        if first_gear != 1:
            path, info = backout_path(node, start, lane)
            if info:
                return path, info
    return None, None


def execute_parking(node, dock, report):
    first_gear = None
    for _ in range(8):
        start = node.checked_pose()
        path, info = straight_finish(node, start, dock)
        if info is None:
            path, info = find_parking_path(node, start, dock, first_gear)
        if info is None and first_gear is not None:
            # The stopped estimate can be short of the intended cusp. Extend
            # the current gear only if a new complete route passes the audit.
            path, info = find_parking_path(node, start, dock, -first_gear)
        if info is None:
            raise RuntimeError("no safe parking route from the stopped AMCL pose")
        report["parking_plans"].append(dict(start=start.tolist(), preferred_gear=first_gear, **info))
        parts = direction_parts(path)
        final = len(parts) == 1
        gear, points, length = parts[0]
        node.drive_leg("parking", gear, points, length, final, report["legs"])
        if final:
            return
        first_gear = -gear
    raise RuntimeError("parking reached its direction-change limit")
