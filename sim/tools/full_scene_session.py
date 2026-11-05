"""Foreground owner of exactly one paused full-model Gazebo and ROS launch.

Never attaches to, controls, or stops an existing simulator. Signals target
only process groups created here with start_new_session=True.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from check_full_entry import check_entry, validate_args

ROOT = Path('/mnt/d/rob-memory')
REPORTS = Path('/home/aphelios/hz_sim_ws/reports')
LOG_ROOT = ROOT / 'outputs/hunter_desktop_restore_20261031/sessions'


def gazebo_command():
    return ['/usr/bin/ign', 'gazebo', '-v', '3', '--render-engine-gui', 'ogre',
            '--gui-config', (ROOT / 'sim/scenes/hz_hunter_full_gui.config').as_posix(),
            (ROOT / 'sim/scenes/hz_hunter_full.sdf').as_posix()]


def ros_command():
    return ['ros2', 'launch', (ROOT / 'sim/launch/hunter_full_ros.launch.py').as_posix()]


def has_existing_world(services):
    return any(line.strip().startswith('/world/') or line.strip() == '/gazebo/worlds'
               for line in services.splitlines())


def ros_node_exited(log_path):
    # launch emits these for a child exit even when the launch parent stays up.
    # Read only the tail, which is enough for a three-node observation launch.
    with Path(log_path).open('rb') as stream:
        stream.seek(max(0, Path(log_path).stat().st_size - 65536))
        tail = stream.read()
    return b']: process has died' in tail or b']: process has finished cleanly' in tail


def group_exists(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


def stop_owned_processes(processes, receipt):
    """The input list contains only successful Popen returns from this session."""
    def send(process, sig):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass

    for process in reversed(processes):
        send(process, signal.SIGINT)
    for process in reversed(processes):
        try:
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            pass
    # A launcher may have exited before its child. Check and finish its own
    # group as well; never discover other groups by program name or service.
    for sig, grace in ((signal.SIGTERM, 2), (signal.SIGKILL, 2)):
        remaining = [process for process in processes if group_exists(process.pid)]
        for process in remaining:
            send(process, sig)
        deadline = time.monotonic() + grace
        while remaining and time.monotonic() < deadline:
            for process in remaining:
                process.poll()  # reap the leader before checking its group
            remaining = [process for process in remaining if group_exists(process.pid)]
            if remaining:
                time.sleep(.05)
    for child, process in zip(receipt['children'], processes):
        child['returncode'] = process.poll()
        child['group_remaining'] = group_exists(process.pid)
        child['closed'] = child['returncode'] is not None and not child['group_remaining']
    receipt['cleanup_complete'] = all(child['closed'] for child in receipt['children'])


def now():
    return datetime.now(timezone.utc).isoformat()


def write_receipt(directory, receipt):
    temporary = directory / 'session.json.tmp'
    temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(directory / 'session.json')


def run_session():
    check = check_entry()
    import fcntl
    if REPORTS.resolve() != REPORTS or REPORTS.parent.resolve() != REPORTS.parent:
        raise ValueError('个人报告目录不是预期的独立路径')
    REPORTS.mkdir(exist_ok=True)
    lock_path = REPORTS / '.full_scene.lock'
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    processes, previous_handlers = [], {}
    receipt = None
    directory = None
    streams = []
    stop = []
    exit_code = 1

    def receive_signal(number, _frame):
        stop.append(number)

    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('已有完整模型会话；请先关闭自己的仿真窗口。') from exc
        os.ftruncate(lock_fd, 0)
        os.write(lock_fd, str(os.getpid()).encode('ascii'))
        if LOG_ROOT.resolve() != LOG_ROOT:
            raise ValueError('日志目录不是预期的 F 盘路径')
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        directory = LOG_ROOT / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid.uuid4().hex[:12])
        directory.mkdir(mode=0o700)
        receipt = {'schema_version': 1, 'started_at_utc': now(), 'supervisor_pid': os.getpid(),
                   'state': 'checking', 'started_paused': True, 'created_pids': [], 'children': [],
                   'startup_arguments': {'gazebo': gazebo_command(), 'ros': ros_command()},
                   'environment': check['environment'], 'entry_check': check,
                   'logs': {'gazebo': str(directory / 'gazebo.log'), 'ros': str(directory / 'ros.log')},
                   'motion_commands_sent': False, 'physics_control_sent': False,
                   'cleanup_complete': False}
        for name in ('gazebo', 'ros'):
            stream = (directory / (name + '.log')).open('wb')
            streams.append(stream)
        write_receipt(directory, receipt)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous_handlers[sig] = signal.signal(sig, receive_signal)
        discovery = subprocess.run(['/usr/bin/ign', 'service', '-l'], capture_output=True,
                                   text=True, encoding='utf-8', timeout=8, check=True)
        (directory / 'services_before.txt').write_text(discovery.stdout + discovery.stderr, encoding='utf-8')
        if has_existing_world(discovery.stdout):
            raise ValueError('个人分区已有仿真；请关闭自己的旧仿真窗口后重试。')
        if stop:
            raise InterruptedError('启动已取消')
        env = dict(os.environ, QSG_INFO='1', QT_LOGGING_RULES='qt.qpa.gl=true',
                   LIBGL_DEBUG='verbose', LANG='C.UTF-8', LC_ALL='C.UTF-8',
                   PYTHONIOENCODING='utf-8', ROS_LOG_DIR=str(directory / 'ros_internal'))
        print('正在打开 HUNTER 完整模型；默认暂停，本轮请勿点击播放。', flush=True)
        print('日志（UTF-8）：' + str(directory), flush=True)
        # Record every successful creation before attempting the next child.
        for role, command, stream in (('ros', ros_command(), streams[1]),
                                      ('gazebo', gazebo_command(), streams[0])):
            if stop:
                raise InterruptedError('启动已取消')
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream,
                                       stderr=subprocess.STDOUT, env=env, start_new_session=True)
            processes.append(process)
            receipt['created_pids'].append(process.pid)
            receipt['children'].append({'role': role, 'pid': process.pid, 'pgid': process.pid,
                                        'created_process_group': True, 'arguments': command})
            write_receipt(directory, receipt)
        receipt['state'] = 'running'
        write_receipt(directory, receipt)
        ros, gazebo = processes
        while True:
            if stop:
                receipt['closing_reason'] = 'signal_' + str(stop[0])
                exit_code = 128 + stop[0]
                break
            if ros.poll() is not None or ros_node_exited(directory / 'ros.log'):
                receipt['closing_reason'] = 'ros_node_exited'
                print('ROS 观察节点已退出，正在关闭本会话的仿真。', file=sys.stderr, flush=True)
                exit_code = 1
                break
            if gazebo.poll() is not None:
                receipt['closing_reason'] = 'gazebo_gui_exited'
                exit_code = 0 if gazebo.returncode == 0 else 1
                break
            time.sleep(.2)
    except BaseException as exc:
        if receipt is not None:
            receipt['closing_reason'] = 'exception'
            receipt['error'] = type(exc).__name__ + ': ' + str(exc)
        print('完整模型会话未继续：' + str(exc), file=sys.stderr, flush=True)
    finally:
        try:
            if receipt is not None:
                receipt['state'] = 'closing'
                # Child cleanup must not depend on the F-drive being writable.
                # A failed startup receipt may be the reason we are here.
                stop_owned_processes(processes, receipt)
                receipt['state'] = 'closed' if receipt['cleanup_complete'] else 'cleanup_incomplete'
                receipt['closed_at_utc'] = now()
                if not receipt['cleanup_complete']:
                    exit_code = 1
                receipt['exit_code'] = exit_code
                try:
                    write_receipt(directory, receipt)
                except Exception as exc:
                    exit_code = receipt['exit_code'] = 1
                    status = '进程组已收尾' if receipt['cleanup_complete'] else '进程组收尾未完成'
                    print('完整模型' + status + '；最终会话记录保存失败：' + str(exc) +
                          '；目标：' + str(directory / 'session.json'), file=sys.stderr, flush=True)
                else:
                    message = '完整模型会话已收尾；记录：' if receipt['cleanup_complete'] else '完整模型会话收尾未完成；记录：'
                    print(message + str(directory / 'session.json'), flush=True)
        finally:
            for stream in streams:
                stream.close()
            for sig, previous in previous_handlers.items():
                signal.signal(sig, previous)
            os.close(lock_fd)
    return exit_code


def main():
    try:
        validate_args(sys.argv[1:])
        return run_session()
    except Exception as exc:
        print('完整模型会话拒绝启动：' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
