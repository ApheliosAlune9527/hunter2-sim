cmake_minimum_required(VERSION 3.8)
project(hunter_description)

find_package(ament_cmake REQUIRED)

# Assets only: no executable, driver, launch file, or control plugin is built.
install(DIRECTORY urdf meshes DESTINATION share/${PROJECT_NAME})

ament_package()
