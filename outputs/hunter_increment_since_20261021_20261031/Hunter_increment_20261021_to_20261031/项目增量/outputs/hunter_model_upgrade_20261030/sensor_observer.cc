// Subscriber-only sensor observer. No service calls, publishers or controls.
#include <gz/transport/Node.hh>
#include <gz/msgs/image.pb.h>
#include <gz/msgs/imu.pb.h>
#include <gz/msgs/laserscan.pb.h>
#include <gz/msgs/pointcloud_packed.pb.h>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <string>

using namespace std::chrono_literals;
namespace msgs = gz::msgs;

struct Sample
{
  unsigned count = 0;
  uint64_t bytes = 0, width = 0, height = 0, finite = 0;
  int64_t stamp = 0;
  std::string frame;
};

struct Observer
{
  std::mutex mutex;
  std::condition_variable changed;
  Sample lidar, points, rgb, depth, imu;
  void Header(Sample &sample, const msgs::Header &header)
  {
    ++sample.count;
    sample.stamp = header.stamp().sec() * 1000000000ll + header.stamp().nsec();
    for (const auto &item : header.data())
      if (item.key() == "frame_id" && item.value_size()) sample.frame = item.value(0);
  }
  void Lidar(const msgs::LaserScan &message)
  {
    std::lock_guard<std::mutex> lock(mutex);
    Header(lidar, message.header()); lidar.width = message.ranges_size();
    lidar.finite = 0;
    for (double value : message.ranges()) if (std::isfinite(value)) ++lidar.finite;
    changed.notify_all();
  }
  void Points(const msgs::PointCloudPacked &message)
  {
    std::lock_guard<std::mutex> lock(mutex);
    Header(points, message.header()); points.width = message.width();
    points.height = message.height(); points.bytes = message.data().size();
    changed.notify_all();
  }
  void Rgb(const msgs::Image &message)
  {
    std::lock_guard<std::mutex> lock(mutex);
    Header(rgb, message.header()); rgb.width = message.width();
    rgb.height = message.height(); rgb.bytes = message.data().size();
    changed.notify_all();
  }
  void Depth(const msgs::Image &message)
  {
    std::lock_guard<std::mutex> lock(mutex);
    Header(depth, message.header()); depth.width = message.width();
    depth.height = message.height(); depth.bytes = message.data().size();
    changed.notify_all();
  }
  void Imu(const msgs::IMU &message)
  {
    std::lock_guard<std::mutex> lock(mutex);
    Header(imu, message.header()); changed.notify_all();
  }
  bool Ready() const
  {
    return lidar.count >= 2 && lidar.finite && points.count >= 2 && points.bytes &&
           rgb.count >= 2 && rgb.bytes && depth.count >= 2 && depth.bytes &&
           imu.count >= 2 && lidar.stamp > 0 && rgb.stamp > 0 && imu.stamp > 0;
  }
};

void print(const char *name, const Sample &sample)
{
  std::cout << std::quoted(name) << ":{\"count\":" << sample.count
            << ",\"bytes\":" << sample.bytes << ",\"width\":" << sample.width
            << ",\"height\":" << sample.height << ",\"finite\":" << sample.finite
            << ",\"stamp_ns\":" << sample.stamp << ",\"frame\":" << std::quoted(sample.frame) << "}";
}

int main(int argc, char **argv)
{
  if (argc != 2) return 2;
  std::string prefix = argv[1];
  if (prefix != "/hz_probe" && prefix != "/hz_sim/full") return 2;
  Observer observer;
  gz::transport::Node node;
  if (!node.Subscribe(prefix + "/lidar", &Observer::Lidar, &observer) ||
      !node.Subscribe(prefix + "/lidar/points", &Observer::Points, &observer) ||
      !node.Subscribe(prefix + "/camera/image", &Observer::Rgb, &observer) ||
      !node.Subscribe(prefix + "/camera/depth_image", &Observer::Depth, &observer) ||
      !node.Subscribe(prefix + "/imu", &Observer::Imu, &observer)) return 3;
  std::unique_lock<std::mutex> lock(observer.mutex);
  observer.changed.wait_for(lock, 20s, [&] { return observer.Ready(); });
  const bool ok = observer.Ready();
  std::cout << "{\"ok\":" << (ok ? "true" : "false") << ",";
  print("lidar", observer.lidar); std::cout << ",";
  print("points", observer.points); std::cout << ",";
  print("rgb", observer.rgb); std::cout << ",";
  print("depth", observer.depth); std::cout << ",";
  print("imu", observer.imu); std::cout << "}" << std::endl;
  return ok ? 0 : 1;
}
