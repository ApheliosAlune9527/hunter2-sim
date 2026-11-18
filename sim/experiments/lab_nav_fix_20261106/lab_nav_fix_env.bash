# Lab navigation environment.
#
# The shared simulator environment caps the CycloneDDS participant index at the
# default of 10, but one Nav2 bringup already uses six participants (map_server,
# planner, controller, behaviour, bt_navigator, lifecycle manager) plus the bridge,
# the truth locator and any CLI tool.  Widening the index space keeps ROS from
# failing with "Failed to find a free participant index for domain 73".
#
# Every failure here is fatal and returns non-zero, so a caller that does
# `source ... || exit 1` stops before anything moves.  A half-loaded environment is
# worse than none: it looks like ROS is broken while the real problem is that the
# simulator variables were never set.

_fix_env_fail() {
  echo "[env] FATAL: $*" >&2
  # `return` works when sourced; fall back to exit when executed directly.
  return 1 2>/dev/null || exit 1
}

# The simulator runs as the personal WSL user; anything else would write logs and
# Gazebo partitions into a different account than the one the records belong to.
_who=$(id -un 2>/dev/null || true)
if [ "$_who" != "aphelios" ]; then
  _fix_env_fail "expected user aphelios, running as '${_who:-unknown}'"
fi

if [ ! -r /mnt/d/rob-memory/wsl/hz_sim_env.bash ]; then
  _fix_env_fail "/mnt/d/rob-memory/wsl/hz_sim_env.bash is missing or unreadable"
fi
# shellcheck disable=SC1091
source /mnt/d/rob-memory/wsl/hz_sim_env.bash || _fix_env_fail "sourcing hz_sim_env.bash failed"

# The isolation is the point: domain 73 + localhost + a private Gazebo partition
# cannot reach the real vehicle on domain 88.  If any of these is wrong the stack
# must not start.
[ "${ROS_DOMAIN_ID:-}" = "73" ] || \
  _fix_env_fail "ROS_DOMAIN_ID is '${ROS_DOMAIN_ID:-unset}', expected 73"
[ "${ROS_LOCALHOST_ONLY:-}" = "1" ] || \
  _fix_env_fail "ROS_LOCALHOST_ONLY is '${ROS_LOCALHOST_ONLY:-unset}', expected 1"
[ "${RMW_IMPLEMENTATION:-}" = "rmw_cyclonedds_cpp" ] || \
  _fix_env_fail "RMW_IMPLEMENTATION is '${RMW_IMPLEMENTATION:-unset}', expected rmw_cyclonedds_cpp"
[ -n "${IGN_PARTITION:-}" ] || _fix_env_fail "IGN_PARTITION is unset"

export CYCLONEDDS_URI='<CycloneDDS><Domain><Discovery><MaxAutoParticipantIndex>64</MaxAutoParticipantIndex></Discovery></Domain></CycloneDDS>'

unset _who
