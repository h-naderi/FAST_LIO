#!/usr/bin/python3
"""Lean live FAST_LIO launch for the Go2 (Hesai XT16, no camera).

Differs from mapping_go2.launch.py in three ways:

  1. IMU: starts ONLY go2_driver/lowstate_to_imu (-> /imu/data), which is what
     hesai_xt16_go2.yaml reads. imu.launch.py also starts imu_calib_republisher
     (~81% CPU, bad calibration) and imu_filter_madgwick (~13% CPU); FAST_LIO
     subscribes to neither of their topics.

  2. Shutdown: the mapper is a plain launch_ros Node, i.e. the binary is
     launch's direct child. The old `bash -c 'ros2 run ... | tee'` wrapper does
     not forward SIGINT, so FAST_LIO never reached its post-spin PCD save and
     launch escalated to SIGKILL. sigterm/sigkill timeouts are raised so a large
     map can be written.

  3. LiDAR time offset: `lidar_time_offset` overrides
     common.time_offset_lidar_to_imu. The Hesai driver stamps the scan START
     since 2026-09-29, so the live value is 0.0 (the YAML's -0.11 compensated
     for the old scan-end stamps).

Usage:
  ros2 launch fast_lio mapping_go2_lean.launch.py use_rviz:=True
  ros2 launch fast_lio mapping_go2_lean.launch.py save_pcd:=true   # PCD/scans.pcd on Ctrl+C
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    share_dir = get_package_share_directory('fast_lio')
    default_config = os.path.join(share_dir, 'config', 'hesai_xt16_go2.yaml')
    rviz_config = os.path.join(share_dir, 'rviz', 'fastlio.rviz')

    use_rviz_arg = DeclareLaunchArgument(
        'use_rviz', default_value='False', description='Launch RViz2')

    params_file_arg = DeclareLaunchArgument(
        'params_file', default_value=default_config,
        description='FAST_LIO parameter file')

    lidar_time_offset_arg = DeclareLaunchArgument(
        'lidar_time_offset', default_value='0.0',
        description='common.time_offset_lidar_to_imu. 0.0 for the fixed Hesai driver '
                    '(scan-start stamps); -0.11 for pre-2026-09-29 scan-end stamps')

    save_pcd_arg = DeclareLaunchArgument(
        'save_pcd', default_value='false',
        description='pcd_save.pcd_save_en: accumulate the map and write PCD/scans.pcd on Ctrl+C')

    # ── 1. IMU (t=0s): raw /lowstate -> /imu/data. No calib republisher, no madgwick. ──
    imu_node = Node(
        package='go2_driver',
        executable='lowstate_to_imu',
        name='lowstate_to_imu',
        output='screen'
    )

    # ── 2. Hesai XT16 LiDAR driver (t=3s) -> /lidar_points ──
    lidar_delayed = TimerAction(period=3.0, actions=[
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution([FindPackageShare('hesai_lidar_driver'), 'launch', 'start.py'])
            )
        )
    ])

    # ── 3. FAST_LIO (t=6s). Direct child of launch so SIGINT reaches it. ──
    mapping_delayed = TimerAction(period=6.0, actions=[
        Node(
            package='fast_lio',
            executable='fastlio_mapping',
            name='laser_mapping',
            parameters=[
                LaunchConfiguration('params_file'),
                # Later entries win, so these override the YAML.
                {'common.time_offset_lidar_to_imu':
                    ParameterValue(LaunchConfiguration('lidar_time_offset'), value_type=float)},
                {'pcd_save.pcd_save_en':
                    ParameterValue(LaunchConfiguration('save_pcd'), value_type=bool)},
            ],
            output='screen',
            # Defaults are 5 s + 5 s; writing a large PCD takes longer than that.
            sigterm_timeout='90',
            sigkill_timeout='60',
        )
    ])

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
        lidar_time_offset_arg,
        save_pcd_arg,
        imu_node,
        lidar_delayed,
        mapping_delayed,
        rviz_node,
    ])
