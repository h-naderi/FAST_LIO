#!/usr/bin/python3
"""Bag-replay variant of mapping_go2.launch.py.

Launches only the FAST_LIO mapping node — no sensor drivers (IMU / Hesai).
Topics come from ros2 bag play instead.

Usage:
  # Terminal A
  ros2 launch fast_lio mapping_go2_bag.launch.py
  # Terminal B
  source /opt/ros/foxy/setup.bash && source ~/fastlivo_ws/install/setup.bash && \
    LD_LIBRARY_PATH=/home/unitree/cyclonedds_ws/install/cyclonedds/lib:$LD_LIBRARY_PATH \
    ros2 bag play ~/fastlivo_ws/rosbags_go2/go2_indoor_apartment --rate 0.5
"""

import os
import datetime
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction, ExecuteProcess, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from ament_index_python.packages import get_package_share_directory
from launch_ros.actions import Node

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_LOG_DIR = os.path.join(_REPO_DIR, 'logs')


def _launch_mapping(context, *args, **kwargs):
    os.makedirs(_LOG_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(_LOG_DIR, f'fastlio_bag_{timestamp}.log')

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

    mapping_delayed = TimerAction(
        period=1.0,
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
        mapping_delayed,
        rviz_node,
    ])
