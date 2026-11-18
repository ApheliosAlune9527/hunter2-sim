"""Distance from the oriented rear-axle footprint to the scene's static boxes."""

import math
import xml.etree.ElementTree as ET

import numpy as np


FOOTPRINT = np.array([[-0.184, -0.393], [0.834, -0.393],
                      [0.834, 0.393], [-0.184, 0.393]])
CORNER_SIGNS = np.array([[-1, -1], [1, -1], [1, 1], [-1, 1]])


def angle(yaw):
    return math.atan2(math.sin(yaw), math.cos(yaw))


def rotation(yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([[c, -s], [s, c]])


def _translation(element):
    pose = element.find("pose")
    if pose is None:
        return np.zeros(3)
    values = np.fromstring(pose.text, sep=" ")
    if pose.attrib or len(values) != 6 or np.any(values[3:]):
        raise ValueError(f"expected an axis-aligned pose on {element.get('name')}")
    return values[:3]


class SceneClearance:
    def __init__(self, sdf):
        self.names = []
        self.kinds = []
        centres, half_sizes = [], []
        world = ET.parse(sdf).getroot().find("world")
        for model in world.findall("model"):
            name = model.get("name")
            if name not in ("walls", "red_sign", "blue_near", "blue_far"):
                continue
            for link in model.findall("link"):
                physical = link.findall("collision")
                for box in physical or link.findall("visual"):
                    size = np.fromstring(box.findtext("geometry/box/size"), sep=" ")
                    centre = _translation(model) + _translation(link) + _translation(box)
                    self.names.append(f"{name}/{box.get('name')}")
                    self.kinds.append("collider" if physical else "visual_keepout")
                    centres.append(centre[:2])
                    half_sizes.append(size[:2] / 2)
        if not centres:
            raise ValueError("no known obstacle rectangles found")
        self.centres = np.array(centres)
        self.half_sizes = np.array(half_sizes)
        self.corners = self.centres[:, None, :] + self.half_sizes[:, None, :] * CORNER_SIGNS

    def at(self, pose, padding=0.0):
        xy = np.asarray(pose[:2])
        rot = rotation(pose[2])
        low = FOOTPRINT.min(axis=0) - padding
        high = FOOTPRINT.max(axis=0) + padding
        vehicle_corners = (np.where(CORNER_SIGNS > 0, high, low) @ rot.T) + xy
        vehicle_half = (high - low) / 2
        vehicle_center = xy + rot @ ((low + high) / 2)
        delta = self.centres - vehicle_center
        world_axes = self.half_sizes + (np.abs(rot) @ vehicle_half) - np.abs(delta)
        lower_bound = np.linalg.norm(np.maximum(-world_axes, 0), axis=1)
        # Seed the bound with an actual pair of points. Boxes farther away by
        # their axis-aligned bounds cannot be the closest rectangle.
        nearest = int(lower_bound.argmin())
        upper_bound = np.linalg.norm(self.corners[nearest] - vehicle_corners[0], axis=1).min()
        ids = np.flatnonzero(lower_bound <= upper_bound)
        local_axes = self.half_sizes[ids] @ np.abs(rot) + vehicle_half - np.abs(delta[ids] @ rot)
        penetration = np.column_stack((world_axes[ids], local_axes)).min(axis=1)
        obs_vertices = (self.corners[ids] - xy) @ rot
        obs_outside = np.maximum(np.maximum(low - obs_vertices, obs_vertices - high), 0)
        robot_outside = np.maximum(
            np.abs(vehicle_corners[None, :, :] - self.centres[ids, None, :])
            - self.half_sizes[ids, None, :], 0)
        distances = np.minimum(np.linalg.norm(obs_outside, axis=2).min(axis=1),
                               np.linalg.norm(robot_outside, axis=2).min(axis=1))
        distances = np.where(penetration >= 0, -penetration, distances)
        i = int(distances.argmin())
        return float(distances[i]), self.names[ids[i]], self.kinds[ids[i]]

    def sweep(self, poses, padding=0.0):
        samples = iter(poses)
        previous = np.asarray(next(samples))
        distance, obstacle, kind = self.at(previous, padding)
        result = dict(clearance_m=distance, obstacle=obstacle, kind=kind, pose=previous.tolist())
        for pose in samples:
            current = np.asarray(pose)
            delta = current - previous
            delta[2] = angle(delta[2])
            count = max(1, math.ceil((np.linalg.norm(delta[:2]) + 0.94 * abs(delta[2])) / 0.015))
            for i in range(1, count + 1):
                sample = previous + delta * (i / count)
                distance, obstacle, kind = self.at(sample, padding)
                if distance < result["clearance_m"]:
                    result = dict(clearance_m=distance, obstacle=obstacle, kind=kind, pose=sample.tolist())
            previous = current
        return result
