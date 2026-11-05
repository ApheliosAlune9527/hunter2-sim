"""Windows-safe offline contracts. Never invoke WSL, ROS or Gazebo."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'outputs/hunter_model_upgrade_20261030/references/entry'
sys.path.insert(0, str(ROOT / 'sim/tools'))


def load_optional(name):
    spec = importlib.util.find_spec(name)
    return __import__(name) if spec else None


entry = load_optional('check_full_entry')
session = load_optional('full_scene_session')


class FullEntryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(entry, 'Full entry guard must exist before launch')
        self.assertIsNotNone(session, 'Owned foreground session supervisor must exist')
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=EVIDENCE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self):
        files = []
        for rel in entry.SEALED_PATHS:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('reviewed ' + rel).encode())
            files.append({'path': rel, 'sha256': entry.sha256(path)})
        return {'schema_version': 1, 'files': files}

    def test_manifest_accepts_only_the_fixed_set(self):
        manifest = self.fixture()
        result = entry.validate_manifest(manifest, self.root)
        self.assertEqual(result['sealed_files'], len(entry.SEALED_PATHS))

    def test_manifest_rejects_missing_extra_duplicate_and_escape(self):
        original = self.fixture()
        variants = []
        missing = copy.deepcopy(original)
        missing['files'].pop()
        variants.append(missing)
        extra = copy.deepcopy(original)
        extra['files'].append({'path': 'unapproved.py', 'sha256': '0' * 64})
        variants.append(extra)
        duplicate = copy.deepcopy(original)
        duplicate['files'].append(copy.deepcopy(duplicate['files'][0]))
        variants.append(duplicate)
        for bad_path in ('../outside', '/tmp/outside', 'C:/outside', r'..\outside',
                         'sim/../outside', '//server/share'):
            escaped = copy.deepcopy(original)
            escaped['files'][0]['path'] = bad_path
            variants.append(escaped)
        for variant in variants:
            with self.subTest(variant=variant['files'][0]['path'], length=len(variant['files'])):
                with self.assertRaises(ValueError):
                    entry.validate_manifest(variant, self.root)

    def test_manifest_rejects_content_change_and_malformed_hash(self):
        manifest = self.fixture()
        (self.root / entry.SEALED_PATHS[0]).write_text('changed', encoding='utf-8')
        with self.assertRaises(ValueError):
            entry.validate_manifest(manifest, self.root)
        manifest = self.fixture()
        manifest['files'][0]['sha256'] = 'not-a-hash'
        with self.assertRaises(ValueError):
            entry.validate_manifest(manifest, self.root)

    def install_fixture(self):
        source, installed = self.root / 'source', self.root / 'installed'
        source.mkdir()
        installed.mkdir()
        outputs = []
        for name in ('CMakeLists.txt', 'package.xml', 'urdf/hunter_full.urdf', 'meshes/a.stl'):
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('source ' + name, encoding='utf-8')
            outputs.append({'path': name, 'sha256': entry.sha256(target)})
            if name != 'CMakeLists.txt':
                target = installed / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((source / name).read_bytes())
        manifest = {'outputs': outputs}
        for base in (source, installed):
            (base / 'source_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        return source, installed, manifest

    def test_installed_share_only_exempts_build_time_cmake(self):
        source, installed, manifest = self.install_fixture()
        result = entry.validate_installed_outputs(source, installed, manifest)
        self.assertEqual(result['not_installed_build_files'], ['CMakeLists.txt'])
        self.assertEqual(result['installed_outputs'], 3)
        self.assertTrue(result['source_manifest_equal'])

    def test_installed_symlink_target_only_allows_same_relative_native_file(self):
        self.assertTrue(hasattr(entry, 'validate_installed_target'),
                        'colcon symlink-install requires an exact native-target guard')
        share = Path('/home/aphelios/hz_sim_ws/install/hz_hunter_full_description/share/hz_hunter_full_description')
        native = Path('/home/aphelios/hz_sim_ws/src/hz_hunter_full_description')
        relative = 'meshes/chassis/base_link.stl'
        self.assertEqual(entry.validate_installed_target(relative, native / relative, share), native / relative)
        self.assertEqual(entry.validate_installed_target(relative, share / relative, share), share / relative)
        for target in (native / 'meshes/chassis/other.stl', Path('/tmp') / relative,
                       native.parent / 'unapproved' / relative):
            with self.assertRaises(ValueError):
                entry.validate_installed_target(relative, target, share)
        with self.assertRaises(ValueError):
            entry.validate_installed_target('../escape', native / 'escape', share)

    def test_symlink_install_checks_native_target_and_exact_bytes(self):
        self.assertTrue(hasattr(entry, 'validate_installed_target'),
                        'symlink-install must not weaken the entry manifest gate')
        source, installed, manifest = self.install_fixture()
        native = self.root / 'native'
        (native / 'meshes').mkdir(parents=True)
        native_file = native / 'meshes/a.stl'
        native_file.write_bytes((source / 'meshes/a.stl').read_bytes())
        installed_file = installed / 'meshes/a.stl'
        installed_file.unlink()
        try:
            installed_file.symlink_to(native_file)
        except OSError as exc:
            self.skipTest('Windows symlink privilege unavailable; exact-target pure test still runs: ' + str(exc))
        entry.validate_installed_outputs(source, installed, manifest, native_source=native)
        native_file.write_bytes(b'wrong native bytes')
        with self.assertRaises(ValueError):
            entry.validate_installed_outputs(source, installed, manifest, native_source=native)
        wrong = native / 'meshes/wrong.stl'
        wrong.write_bytes((source / 'meshes/a.stl').read_bytes())
        installed_file.unlink()
        installed_file.symlink_to(wrong)
        with self.assertRaises(ValueError):
            entry.validate_installed_outputs(source, installed, manifest, native_source=native)

    def test_source_or_install_change_and_missing_resource_rejected(self):
        source, installed, manifest = self.install_fixture()
        (installed / 'meshes/a.stl').write_text('stale', encoding='utf-8')
        with self.assertRaises(ValueError):
            entry.validate_installed_outputs(source, installed, manifest)
        (installed / 'meshes/a.stl').unlink()
        with self.assertRaises(ValueError):
            entry.validate_installed_outputs(source, installed, manifest)
        (source / 'CMakeLists.txt').write_text('changed source', encoding='utf-8')
        with self.assertRaises(ValueError):
            entry.validate_installed_outputs(source, installed, manifest)

    def test_manifest_install_copy_and_unsafe_outputs_rejected(self):
        source, installed, manifest = self.install_fixture()
        (installed / 'source_manifest.json').write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError):
            entry.validate_installed_outputs(source, installed, manifest)
        manifest['outputs'][0]['path'] = '../CMakeLists.txt'
        with self.assertRaises(ValueError):
            entry.validate_installed_outputs(source, installed, manifest)

    def test_environment_and_share_fail_closed(self):
        env = {'WSL_DISTRO_NAME': 'Ubuntu-22.04', 'ROS_DISTRO': 'humble',
               'ROS_DOMAIN_ID': '73', 'ROS_LOCALHOST_ONLY': '1',
               'RMW_IMPLEMENTATION': 'rmw_cyclonedds_cpp',
               'IGN_PARTITION': 'hz_sim_aphelios_73', 'IGN_IP': '127.0.0.1'}
        entry.validate_environment(env, 'microsoft-wsl2', 'aphelios')
        for name, value in [('IGN_IP', '0.0.0.0'), ('IGN_PARTITION', 'default'),
                            ('ROS_DOMAIN_ID', '0'), ('IGN_GAZEBO_SYSTEM_PLUGIN_PATH', '/tmp')]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                entry.validate_environment(dict(env, **{name: value}), 'microsoft-wsl2', 'aphelios')
        with self.assertRaises(ValueError):
            entry.validate_share_path('/opt/ros/humble/share/hz_hunter_full_description')

    def test_entry_argument_contracts_do_not_invoke_programs(self):
        for args in (['-r'], ['--check', '-r'], ['arbitrary.sdf'], ['--help'], ['--check', 'extra']):
            with self.subTest(args=args), patch('subprocess.Popen') as popen, patch('subprocess.run') as run:
                with self.assertRaises(ValueError):
                    entry.validate_args(args, allow_check=True)
                with self.assertRaises(ValueError):
                    session.validate_args(args)
                popen.assert_not_called()
                run.assert_not_called()
        self.assertEqual(entry.validate_args([], allow_check=True), False)
        self.assertEqual(entry.validate_args(['--check'], allow_check=True), True)
        with self.assertRaises(ValueError):
            session.validate_args(['--check'])

    def test_bash_refuses_before_environment_and_legacy_redirects(self):
        for name in ('start_hunter_full_scene.bash', 'start_control_scene_logged.bash'):
            text = (ROOT / 'sim/tools' / name).read_text(encoding='utf-8')
            refusal = text.index('if [[ $# -gt 1 ]]')
            end = text.index('\nfi', refusal)
            self.assertIn('"$1" != \'--check\'', text[refusal:end])
            self.assertIn('exit 1', text[refusal:end])
            self.assertNotIn('source ', text[:end])
        old = (ROOT / 'sim/tools/start_control_scene_logged.ps1').read_text(encoding='utf-8')
        self.assertIn('start_hunter_full_scene.ps1', old)
        self.assertNotIn('start_control_scene.bash', old)
        self.assertIn('start_hunter_full_scene.bash',
                      (ROOT / 'sim/tools/start_control_scene_logged.bash').read_text(encoding='utf-8'))

    @unittest.skipUnless(os.name == 'nt' and Path('F:/w64devkit/bin/bash.exe').is_file(),
                         'Requires the explicit Windows offline shell, never WSL bash')
    def test_windows_bash_rejects_dangerous_flags_before_any_source(self):
        for name in ('start_hunter_full_scene.bash', 'start_control_scene_logged.bash'):
            for args in (['-r'], ['--check', '-r'], ['custom.sdf'], ['--check', 'extra']):
                result = subprocess.run(['F:/w64devkit/bin/bash.exe',
                                         str(ROOT / 'sim/tools' / name), *args],
                                        capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('只接受无参数或 --check'.encode(), result.stderr)
                self.assertNotIn(b'hz_sim_env', result.stderr)

    def test_ros_child_exit_is_detected_even_if_launch_parent_lives(self):
        log = self.root / 'ros.log'
        for line, expected in [('[INFO] [launch]: Started\n', False),
            ('[ERROR] [sensor_bridge-1]: process has died [pid 42]\n', True),
            ('[INFO] [scan_converter-3]: process has finished cleanly [pid 43]\n', True)]:
            log.write_text(line, encoding='utf-8')
            self.assertEqual(session.ros_node_exited(log), expected)

    def test_installed_library_gate_only_reads_fixed_files(self):
        plugins, render = self.root / 'plugins', self.root / 'render'
        plugins.mkdir()
        render.mkdir()
        for name in entry.PLUGIN_NAMES:
            (plugins / ('libignition-gazebo6-' + name + '-system.so')).write_bytes(b'offline fixture')
        (render / 'libignition-rendering6-ogre.so').write_bytes(b'offline fixture')
        with patch.object(entry, 'PLUGIN_DIRECTORY', plugins), patch.object(entry, 'RENDER_DIRECTORY', render), \
                patch('subprocess.Popen') as popen, patch('subprocess.run') as run:
            self.assertEqual(len(entry.check_installed_libraries()), 8)
            (plugins / 'libignition-gazebo6-sensors-system.so').unlink()
            with self.assertRaises(ValueError):
                entry.check_installed_libraries()
            popen.assert_not_called()
            run.assert_not_called()

    def test_existing_world_refuses_without_creating_or_signalling_processes(self):
        fake_fcntl = types.SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=lambda *args: None)
        reports, logs = self.root / 'reports', self.root / 'logs'
        check = {'environment': {'IGN_PARTITION': 'hz_sim_aphelios_73'}}
        with patch.dict(sys.modules, {'fcntl': fake_fcntl}), \
                patch.object(session, 'check_entry', return_value=check), \
                patch.object(session, 'REPORTS', reports), patch.object(session, 'LOG_ROOT', logs), \
                patch.object(session.os, 'O_NOFOLLOW', 0, create=True), \
                patch.object(session.os, 'killpg', create=True) as killpg, \
                patch.object(session.signal, 'SIGHUP', 1, create=True), \
                patch.object(session.signal, 'SIGKILL', 9, create=True), \
                patch.object(session.signal, 'signal'), \
                patch('subprocess.run', return_value=types.SimpleNamespace(
                    stdout='/world/old/control\n', stderr='')) as discover, \
                patch('subprocess.Popen') as popen, patch('builtins.print'):
            self.assertEqual(session.run_session(), 1)
            discover.assert_called_once()
            self.assertEqual(discover.call_args.args[0], ['/usr/bin/ign', 'service', '-l'])
            popen.assert_not_called()
            killpg.assert_not_called()
        receipt = json.loads(next(logs.glob('*/session.json')).read_text(encoding='utf-8'))
        self.assertEqual(receipt['created_pids'], [])
        self.assertTrue(receipt['cleanup_complete'])
        self.assertEqual(receipt['state'], 'closed')

    @unittest.skipUnless(os.name == 'nt', 'PowerShell binding test runs on Windows only')
    def test_powershell_bad_flags_are_rejected_before_wsl(self):
        path = ROOT / 'sim/tools/start_hunter_full_scene.ps1'
        text = path.read_text(encoding='utf-8')
        self.assertIn('PositionalBinding=$false', text)
        for args in (['-r'], ['-Check', 'arbitrary.sdf'], ['-Check', '-r']):
            result = subprocess.run(['powershell.exe', '-NoProfile', '-File', str(path), *args],
                                    capture_output=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(b'NamedParameterNotFound' in result.stderr or
                            b'PositionalParameterNotFound' in result.stderr, result.stderr)

    def test_fixed_paused_commands_and_existing_world_refusal(self):
        command = session.gazebo_command()
        self.assertEqual(command, ['/usr/bin/ign', 'gazebo', '-v', '3',
            '--render-engine-gui', 'ogre', '--gui-config',
            '/mnt/d/rob-memory/sim/scenes/hz_hunter_full_gui.config',
            '/mnt/d/rob-memory/sim/scenes/hz_hunter_full.sdf'])
        self.assertEqual(session.ros_command(), ['ros2', 'launch',
                         '/mnt/d/rob-memory/sim/launch/hunter_full_ros.launch.py'])
        self.assertTrue(session.has_existing_world('/world/old/control\n/other'))
        self.assertTrue(session.has_existing_world('/gazebo/worlds\n'))
        self.assertFalse(session.has_existing_world('/other\n'))

    def test_cleanup_only_signals_owned_created_groups(self):
        class FakeProcess:
            def __init__(self, pid):
                self.pid = pid
                self.returncode = None
            def poll(self):
                return self.returncode
            def wait(self, timeout=None):
                self.returncode = 0
                return 0
        process = FakeProcess(21456)
        receipt = {'children': [{'pid': process.pid, 'role': 'gazebo', 'created_process_group': True}]}
        with patch.object(session.os, 'killpg', create=True) as signal_group, \
                patch.object(session, 'group_exists', return_value=False), \
                patch.object(session.signal, 'SIGKILL', 9, create=True):
            session.stop_owned_processes([process], receipt)
        self.assertEqual(signal_group.call_args_list[0].args[0], process.pid)
        self.assertTrue(all(call.args[0] == process.pid for call in signal_group.call_args_list))
        self.assertEqual(receipt['children'][0]['returncode'], 0)

    def test_partial_launch_failure_cleans_only_successfully_created_group(self):
        fake_fcntl = types.SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=lambda *args: None)
        reports, logs = self.root / 'reports', self.root / 'logs'
        process = types.SimpleNamespace(pid=65432, wait=lambda timeout: 0, poll=lambda: 0)
        check = {'environment': {'IGN_PARTITION': 'hz_sim_aphelios_73'}}
        with patch.dict(sys.modules, {'fcntl': fake_fcntl}), \
                patch.object(session, 'check_entry', return_value=check), \
                patch.object(session, 'REPORTS', reports), patch.object(session, 'LOG_ROOT', logs), \
                patch.object(session.os, 'O_NOFOLLOW', 0, create=True), \
                patch.object(session.os, 'killpg', create=True) as killpg, \
                patch.object(session, 'group_exists', return_value=False), \
                patch.object(session.signal, 'SIGHUP', 1, create=True), \
                patch.object(session.signal, 'SIGKILL', 9, create=True), \
                patch.object(session.signal, 'signal'), \
                patch('subprocess.run', return_value=types.SimpleNamespace(stdout='', stderr='')), \
                patch('subprocess.Popen', side_effect=[process, OSError('fixture launch failure')]) as popen, \
                patch('builtins.print'):
            self.assertEqual(session.run_session(), 1)
            self.assertEqual(popen.call_count, 2)
            self.assertTrue(all(call.kwargs['start_new_session'] for call in popen.call_args_list))
            self.assertEqual(killpg.call_args_list[0].args[0], process.pid)
            self.assertTrue(all(call.args[0] == process.pid for call in killpg.call_args_list))
        receipt = json.loads(next(logs.glob('*/session.json')).read_text(encoding='utf-8'))
        self.assertEqual(receipt['created_pids'], [65432])
        self.assertEqual(receipt['closing_reason'], 'exception')
        self.assertEqual(receipt['state'], 'closed')
        self.assertTrue(receipt['cleanup_complete'])

    def test_repository_seal_is_current(self):
        path = ROOT / 'sim/tools/hunter_full_entry_manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        entry.validate_manifest(manifest, ROOT)

    def exercise_receipt_failure(self, mode):
        fake_fcntl = types.SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=lambda *args: None)
        reports, logs = self.root / 'reports', self.root / 'logs'
        check = {'environment': {'IGN_PARTITION': 'hz_sim_aphelios_73'}}

        class FakeProcess:
            def __init__(self, pid, returncode=None):
                self.pid, self.returncode = pid, returncode
            def poll(self):
                return self.returncode
            def wait(self, timeout=None):
                self.returncode = 0
                return 0

        ros, gazebo = FakeProcess(76541), FakeProcess(76542, returncode=0)
        real_write = session.write_receipt
        real_cleanup = session.stop_owned_processes
        attempted = []

        def failing_write(directory, receipt):
            attempted.append(copy.deepcopy(receipt))
            count = len(receipt['children'])
            if ((mode == 'after_first' and count >= 1) or
                    (mode == 'after_both' and count >= 2) or
                    (mode == 'final' and receipt['state'] == 'closed')):
                raise OSError('fixture disk full')
            real_write(directory, receipt)

        def cleanup_with_result(processes, receipt):
            real_cleanup(processes, receipt)
            if mode == 'cleanup_incomplete':
                receipt['cleanup_complete'] = False

        caught, exit_code = None, None
        with patch.dict(sys.modules, {'fcntl': fake_fcntl}), \
                patch.object(session, 'check_entry', return_value=check), \
                patch.object(session, 'REPORTS', reports), patch.object(session, 'LOG_ROOT', logs), \
                patch.object(session.os, 'O_NOFOLLOW', 0, create=True), \
                patch.object(session.os, 'killpg', create=True) as killpg, \
                patch.object(session, 'group_exists', return_value=False), \
                patch.object(session.signal, 'SIGHUP', 1, create=True), \
                patch.object(session.signal, 'SIGKILL', 9, create=True), \
                patch.object(session.signal, 'signal'), \
                patch('subprocess.run', return_value=types.SimpleNamespace(stdout='', stderr='')), \
                patch('subprocess.Popen', side_effect=[ros, gazebo]) as popen, \
                patch.object(session, 'write_receipt', side_effect=failing_write), \
                patch.object(session, 'stop_owned_processes', side_effect=cleanup_with_result) as cleanup, \
                patch('builtins.print') as printed:
            try:
                exit_code = session.run_session()
            except BaseException as exc:
                caught = exc
            self.assertTrue(cleanup.called, 'Disk-full receipt write must never skip owned-group cleanup')
            cleanup.assert_called_once()
            self.assertIsNone(caught, 'Receipt persistence failure must be handled after child cleanup')
            self.assertEqual(exit_code, 1)
            count = 1 if mode == 'after_first' else 2
            self.assertEqual(popen.call_count, count)
            self.assertEqual({call.args[0] for call in killpg.call_args_list},
                             {process.pid for process in [ros, gazebo][:count]})
            self.assertTrue(all(process.returncode == 0 for process in [ros, gazebo][:count]))
            messages = [str(call.args[0]) for call in printed.call_args_list]
            expected_message = '收尾未完成' if mode == 'cleanup_incomplete' else '记录保存失败'
            self.assertTrue(any(expected_message in message for message in messages))
            self.assertFalse(any('已收尾；记录：' in message for message in messages))
        if mode == 'cleanup_incomplete':
            self.assertFalse(attempted[-1]['cleanup_complete'])
            self.assertEqual(attempted[-1]['exit_code'], 1)
            self.assertEqual(attempted[-1]['state'], 'cleanup_incomplete')
        else:
            self.assertTrue(attempted[-1]['cleanup_complete'])

    def test_disk_full_after_first_child_still_cleans_created_group(self):
        self.exercise_receipt_failure('after_first')

    def test_disk_full_after_both_children_still_cleans_both_groups(self):
        self.exercise_receipt_failure('after_both')

    def test_final_receipt_failure_returns_failure_after_child_cleanup(self):
        self.exercise_receipt_failure('final')

    def test_cleanup_incomplete_receipt_and_console_report_failure(self):
        self.exercise_receipt_failure('cleanup_incomplete')


if __name__ == '__main__':
    unittest.main(verbosity=2)
