// Observe only a private probe camera; no publishing or service calls.
#include <gz/transport/Node.hh>
#include <gz/msgs/image.pb.h>
#include <chrono>
#include <condition_variable>
#include <iostream>
#include <mutex>

using namespace std::chrono_literals;

struct Observer {
  std::mutex mutex;
  std::condition_variable ready;
  bool done = false;
  unsigned count = 0, width = 0, height = 0;
  double x_sum = 0, y_sum = 0;

  void OnImage(const gz::msgs::Image &image) {
    std::lock_guard<std::mutex> lock(mutex);
    if (done || image.width() != 640 || image.height() != 480 ||
        image.step() < image.width() * 3 ||
        image.data().size() < image.step() * image.height()) return;
    width = image.width(); height = image.height();
    const auto &data = image.data();
    for (unsigned y = 0; y < height; ++y) {
      for (unsigned x = 0; x < width; ++x) {
        const auto offset = y * image.step() + x * 3;
        auto r = static_cast<unsigned char>(data[offset]);
        auto g = static_cast<unsigned char>(data[offset + 1]);
        auto b = static_cast<unsigned char>(data[offset + 2]);
        if (r > 70 && r > 2 * g && r > 2 * b && g < 65 && b < 65) {
          ++count; x_sum += x; y_sum += y;
        }
      }
    }
    done = true;
    ready.notify_all();
  }
};

int main() {
  Observer obs;
  gz::transport::Node node;
  if (!node.Subscribe("/hz_camera_probe/camera/image", &Observer::OnImage, &obs)) return 2;
  std::unique_lock<std::mutex> lock(obs.mutex);
  obs.ready.wait_for(lock, 25s, [&] { return obs.done; });
  if (!obs.done || obs.count < 100) return 3;
  std::cout << "{\"red_pixels\":" << obs.count
            << ",\"centroid_x\":" << obs.x_sum / obs.count
            << ",\"centroid_y\":" << obs.y_sum / obs.count
            << ",\"width\":" << obs.width << ",\"height\":" << obs.height
            << "}" << std::endl;
  return 0;
}
