// Message-only fixture. No Gazebo world, actuator, velocity subscription or ROS.
#include <gz/transport/Node.hh>
#include <gz/msgs/boolean.pb.h>
#include <gz/msgs/odometry.pb.h>
#include <gz/msgs/sdf_generator_config.pb.h>
#include <gz/msgs/stringmsg.pb.h>
#include <gz/msgs/world_control.pb.h>
#include <gz/msgs/world_stats.pb.h>
#include <chrono>
#include <fstream>
#include <mutex>
#include <string>
#include <thread>

using namespace std::chrono_literals;
namespace tr = gz::transport;
namespace msgs = gz::msgs;

struct Fixture
{
  std::mutex mutex;
  std::ofstream events;
  std::string mode;
  unsigned reads = 0;
  uint64_t iterations = 0;

  bool Read(const msgs::SdfGeneratorConfig &, msgs::StringMsg &response)
  {
    unsigned number;
    {
      std::lock_guard<std::mutex> lock(mutex);
      number = ++reads;
      events << "{\"operation\":\"read\",\"number\":" << number << "}" << std::endl;
    }
    if (mode == "reject-read") return false;
    // A late read-only reply must never cause a duplicate control request.
    if (mode == "delay-first-read" && number == 1) std::this_thread::sleep_for(6s);
    response.set_data("<sdf version='1.9'/>");
    return true;
  }

  bool Control(const msgs::WorldControl &request, msgs::Boolean &response)
  {
    std::lock_guard<std::mutex> lock(mutex);
    events << "{\"operation\":\"control\",\"reads_before_control\":" << reads
           << ",\"multi_step\":" << request.multi_step() << "}" << std::endl;
    // Model a reply channel that has not yet been established. Only the
    // ordered message exchange is tested; this does not simulate physics.
    const bool ready = reads > 0 && mode != "reject-read";
    response.set_data(ready);
    if (ready) iterations += request.multi_step();
    return ready;
  }
};

int main(int argc, char **argv)
{
  if (argc != 3) return 2;
  Fixture fixture;
  fixture.mode = argv[1];
  fixture.events.open(argv[2]);
  if (!fixture.events) return 2;
  tr::Node node;
  const std::string world = "/world/hz_hunter_control";
  if (!node.Advertise(world + "/generate_world_sdf", &Fixture::Read, &fixture) ||
      !node.Advertise(world + "/control", &Fixture::Control, &fixture)) return 3;
  auto statsPublisher = node.Advertise<msgs::WorldStatistics>(world + "/stats");
  auto odomPublisher = node.Advertise<msgs::Odometry>("/hz_sim/odom");
  for (unsigned tick = 0; tick < 1200; ++tick)
  {
    msgs::WorldStatistics stats;
    {
      std::lock_guard<std::mutex> lock(fixture.mutex);
      stats.set_paused(true);
      stats.set_iterations(fixture.iterations);
      stats.mutable_sim_time()->set_sec(fixture.iterations / 1000);
    }
    msgs::Odometry odom;
    odom.mutable_twist()->mutable_linear()->set_x(0.0);
    statsPublisher.Publish(stats);
    odomPublisher.Publish(odom);
    std::this_thread::sleep_for(50ms);
  }
}
