#!/usr/bin/python3

import os
import datetime
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, IncludeLaunchDescription, TimerAction,
    ExecuteProcess, OpaqueFunction
)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_LOG_DIR = os.path.join(_REPO_DIR, 'logs')


def _launch_mapping(context, *args, **kwargs):
    os.makedirs(_LOG_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(_LOG_DIR, f'fastlio_{timestamp}.log')

    params_file = context.launch_configurations['params_file']

    mapping = ExecuteProcess(
        cmd=[
            'bash', '-c',
            f'ros2 run fast_lio fastlio_mapping '
            f'--ros-args --params-file {params_file} '
            f'2>&1 | tee {log_file}'
        ],
        output='screen'
    )
    return [mapping]


def generate_launch_description():

    config_dir = os.path.join(get_package_share_directory('fast_lio'), 'config')
    default_config = os.path.join(config_dir, 'hesai_xt16_go2.yaml')
    rviz_config = os.path.join(get_package_share_directory('fast_lio'), 'rviz', 'fastlio.rviz')

    use_rviz_arg = DeclareLaunchArgument(
        'use_rviz', default_value='False', description='Launch RViz2')

    params_file_arg = DeclareLaunchArgument(
        'params_file', default_value=default_config,
        description='FAST_LIO parameter file')

    # ── 1. IMU pipeline (t=0s): lowstate → imu_calib_republisher → Madgwick → /imu/filtered ──
    imu_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare('go2_driver'), 'launch', 'imu.launch.py'])
        )
    )

    # ── 2. Hesai XT16 LiDAR driver (t=3s) → /lidar_points ──
    lidar_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare('hesai_lidar_driver'), 'launch', 'start.py'])
        )
    )
    lidar_delayed = TimerAction(period=3.0, actions=[lidar_launch])

    # ── 3. FAST_LIO node (t=6s): IMU + LiDAR both publishing ──
    mapping_delayed = TimerAction(
        period=6.0,
        actions=[OpaqueFunction(function=_launch_mapping)]
    )

    rviz_node = Node(
        condition=IfCondition(LaunchConfiguration('use_rviz')),
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        output='screen'
    )

    return LaunchDescription([
        use_rviz_arg,
        params_file_arg,
        imu_launch,
        lidar_delayed,
        mapping_delayed,
        rviz_node,
    ])
