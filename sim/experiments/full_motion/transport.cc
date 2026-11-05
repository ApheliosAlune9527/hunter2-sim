// Bounded full-model Gazebo-only tests. No ROS / CAN / hardware API.
#include <gz/transport/Node.hh>
#include <gz/msgs/boolean.pb.h>
#include <gz/msgs/model.pb.h>
#include <gz/msgs/odometry.pb.h>
#include <gz/msgs/pose_v.pb.h>
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
#include <iostream>
#include <mutex>
#include <pwd.h>
#include <regex>
#include <stdexcept>
#include <thread>
#include <unistd.h>
using namespace std::chrono_literals;
namespace tr=gz::transport; namespace msg=gz::msgs;
void need(bool b,const std::string &s){if(!b)throw std::runtime_error(s);}
std::string env(const char *n){auto v=std::getenv(n);return v?v:"";}
std::string json(const google::protobuf::Message &m){std::string s;google::protobuf::util::JsonPrintOptions o;o.preserve_proto_field_names=true;o.always_print_primitive_fields=true;need(google::protobuf::util::MessageToJsonString(m,&s,o).ok(),"JSON failed");return s;}
struct Watch {
 std::mutex m;std::condition_variable cv; msg::WorldStatistics stats;msg::Odometry odom;msg::Pose pose;msg::Model joints;
 bool haveStats=false,haveOdom=false,havePose=false,haveJoints=false;
 void Stats(const msg::WorldStatistics &x){std::lock_guard<std::mutex> l(m);stats=x;haveStats=true;cv.notify_all();}
 void Odom(const msg::Odometry &x){std::lock_guard<std::mutex> l(m);odom=x;haveOdom=true;cv.notify_all();}
 void Poses(const msg::Pose_V &x){std::lock_guard<std::mutex> l(m);for(const auto &p:x.pose())if(p.name()=="hz_hunter_full"){pose=p;havePose=true;}cv.notify_all();}
 void Joints(const msg::Model &x){std::lock_guard<std::mutex> l(m);joints=x;haveJoints=true;cv.notify_all();}
};
int main(int argc,char **argv){
 try{
  need(argc==3,"token and fixed profile required");std::string token=argv[1],profile=argv[2];
  need(std::regex_match(token,std::regex("[0-9a-f]{12}")),"invalid experiment token");
  need(profile=="straight"||profile=="left"||profile=="right"||profile=="collision"||profile=="full_straight","unapproved profile");
  auto user=getpwuid(getuid());std::ifstream f("/proc/sys/kernel/osrelease");std::string kernel;std::getline(f,kernel);
  need(user&&std::string(user->pw_name)=="aphelios"&&kernel.find("microsoft")!=std::string::npos&&env("WSL_DISTRO_NAME")=="Ubuntu-22.04","not personal WSL");
  need(env("IGN_PARTITION")=="hz_sim_aphelios_73_motion_"+token&&env("IGN_IP")=="127.0.0.1"&&env("IGN_RELAY").empty(),"isolated Gazebo environment required");
  need(env("ROS_DOMAIN_ID")=="73"&&env("ROS_LOCALHOST_ONLY")=="1","personal ROS configuration required");
  const std::string world="/world/hz_full_motion_"+token,topic="/hz_sim/motion/"+token;
  tr::Node node;Watch w;
  auto providers=[&](const std::string &name,const std::string &req,const std::string &rep){
   std::vector<tr::ServicePublisher> p;node.ServiceInfo(name,p);need(p.size()==1,"service missing / ambiguous: "+name);
   need(p[0].Addr().rfind("tcp://127.0.0.1:",0)==0&&p[0].ReqTypeName()==req&&p[0].RepTypeName()==rep,"nonlocal or mistyped service");return p[0];};
  std::this_thread::sleep_for(1500ms);
  auto c=providers(world+"/control","ignition.msgs.WorldControl","ignition.msgs.Boolean");
  auto s=providers(world+"/generate_world_sdf","ignition.msgs.SdfGeneratorConfig","ignition.msgs.StringMsg");
  need(c.PUuid()==s.PUuid()&&c.Addr()==s.Addr(),"read/control server mismatch");
  need(node.Subscribe(world+"/stats",&Watch::Stats,&w),"stats subscription failed");
  need(node.Subscribe(world+"/pose/info",&Watch::Poses,&w),"truth subscription failed");
  need(node.Subscribe(topic+"/odom",&Watch::Odom,&w),"odom subscription failed");
  need(node.Subscribe(topic+"/joint_states",&Watch::Joints,&w),"joint subscription failed");
  {std::unique_lock<std::mutex> l(w.m);need(w.cv.wait_for(l,8s,[&]{return w.haveStats;}),"no stats");need(w.stats.paused()&&w.stats.iterations()==0,"world not freshly paused");}
  bool warmed=false;
  for(int i=0;i<2&&!warmed;i++){msg::SdfGeneratorConfig q;msg::StringMsg a;bool ok=false;if(node.Request(world+"/generate_world_sdf",q,5000u,a,ok)){need(ok&&a.data().find("hz_full_motion_"+token)!=std::string::npos,"wrong running SDF");warmed=true;}}
  need(warmed,"read-only handshake failed; no control request sent");
  std::vector<tr::MessagePublisher> existing;node.TopicInfo(topic+"/cmd_vel",existing);need(existing.empty(),"unexpected command publisher");
  auto pub=node.Advertise<msg::Twist>(topic+"/cmd_vel");need(pub.Valid(),"publisher failed");
  for(int i=0;i<250&&!pub.HasConnections();i++)std::this_thread::sleep_for(20ms);
  need(pub.HasConnections(),"no simulator command subscriber");
  auto command=[&](double v,double z){msg::Twist t;t.mutable_linear()->set_x(v);t.mutable_angular()->set_z(z);for(int i=0;i<5;i++){need(pub.Publish(t),"publish failed");std::this_thread::sleep_for(20ms);}};
  auto step=[&](unsigned count){
   uint64_t begin;{std::lock_guard<std::mutex> l(w.m);need(w.stats.paused(),"must pause before fixed stepping");begin=w.stats.iterations();}
   msg::WorldControl q;q.set_pause(true);q.set_multi_step(count);msg::Boolean a;bool ok=false;
   // Exactly one attempt: a delayed control reply must never duplicate steps.
   need(node.Request(world+"/control",q,5000u,a,ok)&&ok&&a.data(),"control request failed (not retried)");
   std::unique_lock<std::mutex> l(w.m);need(w.cv.wait_for(l,35s,[&]{return w.stats.paused()&&w.stats.iterations()>=begin+count;}),"bounded steps did not finish");
   need(w.stats.iterations()==begin+count,"unexpected simulation steps");l.unlock();std::this_thread::sleep_for(250ms);
  };
  auto snapshot=[&](const std::string &phase){std::lock_guard<std::mutex> l(w.m);need(w.haveOdom&&w.havePose&&w.haveJoints,"missing truth, odom or joint telemetry");std::cout<<"{\"phase\":\""<<phase<<"\",\"stats\":"<<json(w.stats)<<",\"truth\":"<<json(w.pose)<<",\"odom\":"<<json(w.odom)<<",\"joints\":"<<json(w.joints)<<"}"<<std::endl;};
  command(0,0);step(profile=="full_straight"?1000:2000);snapshot("settled");
  command(.1,profile=="left"?.08:(profile=="right"?-.08:0));step(profile=="collision"?10000:(profile=="full_straight"?2000:6000));snapshot("driven");
  command(0,0);step(profile=="full_straight"?1000:3000);snapshot("stopped");
  std::cout<<"{\"completed\":true,\"zero_command_sent\":true,\"paused\":true,\"server_process_uuid\":\""<<c.PUuid()<<"\"}"<<std::endl;
  return 0;
 }catch(const std::exception &e){std::cerr<<e.what()<<std::endl;return 1;}
}
