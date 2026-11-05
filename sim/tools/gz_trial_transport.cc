// Fixed Gazebo-only operations. No ROS, CAN, hardware SDK or user velocity input.
#include <gz/transport/Node.hh>
#include <gz/msgs/boolean.pb.h>
#include <gz/msgs/odometry.pb.h>
#include <gz/msgs/sdf_generator_config.pb.h>
#include <gz/msgs/stringmsg.pb.h>
#include <gz/msgs/twist.pb.h>
#include <gz/msgs/world_control.pb.h>
#include <gz/msgs/world_stats.pb.h>
#include <google/protobuf/util/json_util.h>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <pwd.h>
#include <regex>
#include <stdexcept>
#include <string>
#include <thread>
#include <unistd.h>

using namespace std::chrono_literals;
namespace tr = gz::transport;
namespace msgs = gz::msgs;
const std::string world = "/world/hz_hunter_control";
const std::string commandTopic = "/hz_sim/cmd_vel";

void require(bool valid, const std::string &message)
{
  if (!valid) throw std::runtime_error(message);
}

std::string env(const char *name)
{
  const char *value = std::getenv(name);
  return value ? value : "";
}

std::string json(const google::protobuf::Message &message)
{
  std::string result;
  google::protobuf::util::JsonPrintOptions options;
  options.preserve_proto_field_names = true;
  options.always_print_primitive_fields = true;
  require(google::protobuf::util::MessageToJsonString(message, &result, options).ok(), "JSON serialization failed");
  return result;
}

struct Watcher
{
  std::mutex mutex;
  std::condition_variable changed;
  msgs::WorldStatistics stats;
  msgs::Odometry odom;
  bool hasStats = false, hasOdom = false;
  void OnStats(const msgs::WorldStatistics &message)
  {
    std::lock_guard<std::mutex> lock(mutex);
    stats = message; hasStats = true; changed.notify_all();
  }
  void OnOdom(const msgs::Odometry &message)
  {
    std::lock_guard<std::mutex> lock(mutex);
    odom = message; hasOdom = true; changed.notify_all();
  }
};

std::vector<tr::ServicePublisher> providers(tr::Node &node, const std::string &name,
                                          const std::string &request, const std::string &response)
{
  std::vector<tr::ServicePublisher> values;
  node.ServiceInfo(name, values);
  require(values.size() == 1, "World service is missing or ambiguous");
  require(values[0].Addr().rfind("tcp://127.0.0.1:", 0) == 0 &&
          values[0].ReqTypeName() == request && values[0].RepTypeName() == response,
          "World service address or types do not match the personal simulator");
  return values;
}

void printProviders(const std::vector<tr::ServicePublisher> &values)
{
  std::cout << "[";
  for (size_t index = 0; index < values.size(); ++index)
  {
    if (index) std::cout << ",";
    const auto &p = values[index];
    std::cout << "{\"address\":" << std::quoted(p.Addr())
              << ",\"process_uuid\":" << std::quoted(p.PUuid())
              << ",\"request_type\":" << std::quoted(p.ReqTypeName())
              << ",\"response_type\":" << std::quoted(p.RepTypeName()) << "}";
  }
  std::cout << "]";
}

int main(int argc, char **argv)
{
  try
  {
    require(argc == 2, "One fixed operation is required");
    const std::string operation = argv[1];
    require(operation == "snapshot" || operation == "speed" || operation == "stop" ||
            operation == "step-drive" || operation == "step-stop" || operation == "pause",
            "Unsupported operation");
    std::ifstream kernelFile("/proc/sys/kernel/osrelease");
    std::string kernel; std::getline(kernelFile, kernel);
    auto *user = getpwuid(getuid());
    require(user && std::string(user->pw_name) == "aphelios" &&
            kernel.find("microsoft") != std::string::npos &&
            env("WSL_DISTRO_NAME") == "Ubuntu-22.04", "Only the personal WSL is allowed");
    require(env("ROS_DOMAIN_ID") == "73" && env("ROS_LOCALHOST_ONLY") == "1" &&
            env("RMW_IMPLEMENTATION") == "rmw_cyclonedds_cpp" &&
            env("CYCLONEDDS_URI").empty() && env("IGN_IP") == "127.0.0.1" && env("IGN_RELAY").empty(),
            "Personal environment does not match");
    require(env("IGN_PARTITION") == "hz_sim_aphelios_73" ||
            std::regex_match(env("IGN_PARTITION"), std::regex("hz_sim_aphelios_73_test_[0-9a-f]{12}")),
            "Unexpected Gazebo partition");
    Watcher watcher;
    tr::Node node;
    auto controls = providers(node, world + "/control", "ignition.msgs.WorldControl", "ignition.msgs.Boolean");
    require(node.Subscribe(world + "/stats", &Watcher::OnStats, &watcher), "Cannot subscribe to world stats");
    require(node.Subscribe("/hz_sim/odom", &Watcher::OnOdom, &watcher), "Cannot subscribe to virtual odometry");
    std::unique_lock<std::mutex> lock(watcher.mutex);
    require(watcher.changed.wait_for(lock, 6s, [&] { return watcher.hasStats; }), "No world state received");
    auto initial = watcher.stats;
    lock.unlock();
    if (operation == "snapshot")
    {
      auto generators = providers(node, world + "/generate_world_sdf", "ignition.msgs.SdfGeneratorConfig", "ignition.msgs.StringMsg");
      require(generators[0].PUuid() == controls[0].PUuid(), "Scene and control services belong to different processes");
      msgs::SdfGeneratorConfig request;
      msgs::StringMsg response;
      bool result = false;
      require(node.Request(world + "/generate_world_sdf", request, 5000u, response, result) && result &&
              !response.data().empty(), "Cannot read the running world SDF");
      std::vector<tr::MessagePublisher> publishers;
      node.TopicInfo(commandTopic, publishers);
      std::cout << "{\"stats\":" << json(initial) << ",\"sdf\":" << json(response)
                << ",\"command_publishers\":" << publishers.size() << ",\"control_providers\":";
      printProviders(controls); std::cout << ",\"sdf_providers\":"; printProviders(generators);
      std::cout << "}" << std::endl;
    }
    else if (operation == "speed" || operation == "stop")
    {
      if (operation == "speed") require(initial.paused(), "Positive speed may only be set while paused");
      auto publisher = node.Advertise<msgs::Twist>(commandTopic);
      require(publisher.Valid(), "Cannot create the fixed virtual publisher");
      auto deadline = std::chrono::steady_clock::now() + 5s;
      while (!publisher.HasConnections() && std::chrono::steady_clock::now() < deadline)
        std::this_thread::sleep_for(20ms);
      require(publisher.HasConnections(), "No subscriber connected to the virtual velocity publisher");
      msgs::Twist twist;
      twist.mutable_linear()->set_x(operation == "speed" ? 0.10 : 0.0);
      twist.mutable_angular()->set_z(0.0);
      for (int index = 0; index < 5; ++index)
      {
        require(publisher.Publish(twist), "Virtual target publication failed");
        std::this_thread::sleep_for(20ms);
      }
      std::cout << "{\"ok\":true}" << std::endl;
    }
    else
    {
      msgs::WorldControl request;
      request.set_pause(true);
      const uint64_t count = operation == "step-drive" ? 2000 : (operation == "step-stop" ? 1000 : 0);
      if (count)
      {
        require(initial.paused(), "World must be paused before bounded stepping");
        request.set_multi_step(count);
      }
      // Transport 11 establishes the reverse reply route on the first RPC.
      // Prove that route using a read on this SAME node / response identity
      // before a control request can change the world. A timed-out read may
      // be retried once; a world-control request must never be retried.
      auto generators = providers(node, world + "/generate_world_sdf",
                                  "ignition.msgs.SdfGeneratorConfig", "ignition.msgs.StringMsg");
      require(generators[0].PUuid() == controls[0].PUuid() &&
              generators[0].Addr() == controls[0].Addr(),
              "Read-only handshake does not share the world-control endpoint and process");
      bool replyRouteReady = false;
      unsigned warmupAttempts = 0;
      for (unsigned attempt = 0; attempt < 2 && !replyRouteReady; ++attempt)
      {
        ++warmupAttempts;
        msgs::SdfGeneratorConfig readRequest;
        msgs::StringMsg readResponse;
        bool readResult = false;
        const bool received = node.Request(world + "/generate_world_sdf", readRequest,
                                           5000u, readResponse, readResult);
        if (received)
        {
          require(readResult && !readResponse.data().empty(),
                  "Read-only reply handshake rejected; no world control request sent");
          replyRouteReady = true;
        }
      }
      require(replyRouteReady, "Read-only reply handshake timed out twice; no world control request sent");
      lock.lock();
      if (count)
        require(watcher.stats.paused() && watcher.stats.iterations() == initial.iterations(),
                "World changed during read-only handshake; no bounded step request sent");
      lock.unlock();
      msgs::Boolean response;
      bool result = false;
      // Do not retry this request: a delayed reply may still execute its steps.
      require(node.Request(world + "/control", request, 5000u, response, result),
              "World control reply timed out; one request attempt, not retried");
      require(result && response.data(), "World control request was rejected");
      lock.lock();
      require(watcher.changed.wait_for(lock, 22s, [&] {
        return watcher.stats.paused() && watcher.stats.iterations() >= initial.iterations() + count &&
               (count == 0 || watcher.hasOdom);
      }), "World did not finish its fixed steps and return to pause");
      require(watcher.stats.iterations() == initial.iterations() + count, "Unexpected extra simulation steps");
      std::cout << "{\"ok\":true,\"rpc_warmup_completed\":true,\"rpc_warmup_attempts\":"
                << warmupAttempts << ",\"stats\":" << json(watcher.stats);
      if (count) std::cout << ",\"odom\":" << json(watcher.odom);
      std::cout << "}" << std::endl;
    }
    return 0;
  }
  catch (const std::exception &error)
  {
    std::cerr << error.what() << std::endl;
    return 1;
  }
}
