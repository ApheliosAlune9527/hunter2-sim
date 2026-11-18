# Lab navigation environment.
#
# The shared simulator environment caps the CycloneDDS participant index at the
# default of 10, but one Nav2 bringup already uses six participants (map_server,
# planner, controller, behaviour, bt_navigator, lifecycle manager) plus the bridge,
# the truth locator and any CLI tool. Widening the index space keeps ROS from
# failing with "Failed to find a free participant index for domain 73".
source /mnt/d/rob-memory/wsl/hz_sim_env.bash
export CYCLONEDDS_URI='<CycloneDDS><Domain><Discovery><MaxAutoParticipantIndex>64</MaxAutoParticipantIndex></Discovery></Domain></CycloneDDS>'
