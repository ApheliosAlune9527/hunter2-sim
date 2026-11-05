"""Exercise the native client's reply handshake without any simulated robot."""
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import time
import uuid

from check_ros_isolation import validate_environment


def main():
    validate_environment(os.environ, Path('/proc/sys/kernel/osrelease').read_text(),
                         pwd.getpwuid(os.getuid()).pw_name)
    output = Path('/mnt/d/rob-memory/outputs/hunter_sim_execution_20261012/'
                  'references/transport_reply_checks') / uuid.uuid4().hex[:12]
    output.mkdir(parents=True)
    native = Path('/home/aphelios/hz_sim_ws/tools/gz_trial_transport')
    fixture = Path('/home/aphelios/hz_sim_ws/tools/test_transport_reply_warmup')
    report = {'robot_or_physics_loaded': False, 'velocity_published': False,
              'user_window_targeted': False, 'cases': [], 'report_directory': str(output)}
    for mode in ['warmup-required', 'delay-first-read', 'reject-read']:
        case_dir = output / mode
        case_dir.mkdir()
        environment = dict(os.environ, IGN_PARTITION='hz_sim_aphelios_73_test_' + uuid.uuid4().hex[:12])
        with (case_dir / 'fixture.log').open('wb') as log:
            process = subprocess.Popen([str(fixture), mode, str(case_dir / 'events.jsonl')],
                                       env=environment, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            try:
                time.sleep(0.6)
                result = subprocess.run([str(native), 'step-drive'], env=environment,
                                        capture_output=True, text=True, timeout=50)
                (case_dir / 'native.stdout.txt').write_text(result.stdout)
                (case_dir / 'native.stderr.txt').write_text(result.stderr)
                events = [json.loads(line) for line in (case_dir / 'events.jsonl').read_text().splitlines()]
                reads = [event for event in events if event['operation'] == 'read']
                controls = [event for event in events if event['operation'] == 'control']
                if mode == 'reject-read':
                    passed = result.returncode != 0 and len(reads) == 1 and not controls
                else:
                    expected_reads = 2 if mode == 'delay-first-read' else 1
                    passed = (result.returncode == 0 and len(reads) == expected_reads and
                              len(controls) == 1 and controls[0]['reads_before_control'] == expected_reads and
                              controls[0]['multi_step'] == 2000)
                report['cases'].append({'mode': mode, 'ok': passed,
                                        'native_exit_code': result.returncode,
                                        'read_requests': len(reads), 'control_requests': len(controls),
                                        'error': result.stderr.strip()})
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=5)
    report['ok'] = all(case['ok'] for case in report['cases'])
    (output / 'check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
