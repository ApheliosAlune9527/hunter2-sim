cmake_minimum_required(VERSION 3.8)
project(hz_hunter_sim)
find_package(ament_cmake REQUIRED)

# This checkpoint installs model data only. No driver or node is built.
install(DIRECTORY urdf DESTINATION share/${PROJECT_NAME})
install(FILES README.md DESTINATION share/${PROJECT_NAME})

ament_package()
