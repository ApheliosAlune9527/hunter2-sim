cmake_minimum_required(VERSION 3.8)
project(realsense2_description)

find_package(ament_cmake REQUIRED)

# Repackage only exported model data, without camera drivers or message code.
install(DIRECTORY urdf meshes DESTINATION share/${PROJECT_NAME})

ament_package()
