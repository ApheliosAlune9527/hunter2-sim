"""Pinned sensor-frame settings exported from the personal robot workspace.

The exported C++ and serial publisher are read only for hash verification.
They are never imported or executed. Values reproduce the mapping settings;
they do not establish the physical accuracy of the original calibration.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path


PROFILE_ID = 'car_mapping_20261030'
SOURCE_FILES = {
    'mapping_source': ('robot_assets/car_sensor_config_20261030/xt32_ch104_d435i.yaml',
                       'bd5a59683e9ed914fab81af13af0306a75ab13d5091ce2e3465dad5fea93cb9e'),
    'source_vio': ('robot_assets/car_sensor_config_20261030/source/vio.cpp',
                   '5786aeca9a26c796953430d471d5428279a5590c084b07dc945647aa88048911'),
    'source_livmapper': ('robot_assets/car_sensor_config_20261030/source/LIVMapper.cpp',
                        '1bbdae25fde516032de59371364960481f569fa67f21ab16fb7d6d07034409f8'),
    'source_ch104': ('robot_assets/car_sensor_config_20261030/source/ch104_imu_pub_legacy.py',
                     'abcb19913c42d5133913b72754b2515f9740223a1726af6840c8651fc7f9ed52'),
}
# These values are tied to the exact YAML hash above. The actual source uses
# p_I = R_IL p_L + t_IL and p_C = R_CL p_L + t_CL.
R_IL = ((1., 0., 0.), (0., 1., 0.), (0., 0., 1.))
T_IL = (.110, 0., .062)
R_CL = ((-1., 0., 0.), (0., 0., -1.), (0., -1., 0.))
T_CL = (.015, -.050, -.105)
# Optical +Z is engine +X, optical +X is engine -Y, optical +Y is engine -Z.
R_ENGINE_OPTICAL = ((0., 0., 1.), (-1., 0., 0.), (0., -1., 0.))


def transpose(matrix):
    return tuple(zip(*matrix))


def inverse_pose(translation, rotation):
    rt = transpose(rotation)
    return tuple(-sum(rt[i][j] * translation[j] for j in range(3)) for i in range(3)), rt


def matrix_rpy(matrix):
    return (math.atan2(matrix[2][1], matrix[2][2]),
            math.asin(max(-1., min(1., -matrix[2][0]))),
            math.atan2(matrix[1][0], matrix[0][0]))


def optical_to_engine(translation, rotation):
    inverse_optical = transpose(R_ENGINE_OPTICAL)
    engine = tuple(tuple(sum(rotation[i][k] * inverse_optical[k][j] for k in range(3))
                         for j in range(3)) for i in range(3))
    return translation, engine


def relative_poses():
    """URDF child-frame poses, both expressed in the lidar parent frame."""
    return {'imu_link': inverse_pose(T_IL, R_IL),
            'camera_optical_frame': inverse_pose(T_CL, R_CL)}


def validate_sources(root):
    root = Path(root).resolve()
    records = []
    for role, (relative, expected) in SOURCE_FILES.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Sensor profile source missing or outside workspace: ' + relative)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('Sensor profile source SHA256 mismatch: ' + relative)
        records.append({'role': role, 'path': relative, 'sha256': actual})
    return records


def profile_report(root):
    return {
        'id': PROFILE_ID,
        'status': 'existing mapping settings reused; physical accuracy unverified',
        'sources': validate_sources(root),
        'point_mappings': {'lidar_to_imu': 'p_I = R_IL * p_L + t_IL',
                           'lidar_to_camera': 'p_C = R_CL * p_L + t_CL'},
        'parameters': {'extrinsic_R': [x for row in R_IL for x in row],
                       'extrinsic_T': list(T_IL),
                       'Rcl': [x for row in R_CL for x in row], 'Pcl': list(T_CL)},
        'imu': {'device': 'CH104', 'default_source_frame': 'imu_link',
                'axis_permutation': False, 'acceleration_conversion': 'g multiplied by 9.81',
                'angular_velocity_conversion': 'degrees/s converted to radians/s'},
        'anchor': 'exported nominal hesai_lidar body mounting TF',
        'physical_calibration_verified': False,
        'timing_and_noise_copied': False,
    }
