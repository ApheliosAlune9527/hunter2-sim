"""Headless load check for the lab navigation world (handoff task 1).

Runs three things and reports them separately, because they fail for different
reasons: SDF syntax, mesh resolution and runtime plugin loading.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

WORLD = Path('/mnt/d/rob-memory/outputs/lab_nav_20261105/lab_nav_world.sdf')
PARTITION = 'hz_sim_labnav_check'
ENV = ('source /opt/ros/humble/setup.bash; '
       'source /opt/robostack/setup.bash 2>/dev/null; '
       'source /mnt/d/rob-memory/wsl/hz_sim_env.bash 2>/dev/null; '
       f'export IGN_PARTITION={PARTITION};')


def run(command, timeout):
    return subprocess.run(['bash', '-lc', ENV + ' ' + command],
                          capture_output=True, text=True, timeout=timeout)


def main():
    result = {'world': str(WORLD), 'checks': {}}

    syntax = run(f'ign sdf -k {WORLD}', 120)
    result['checks']['sdf_syntax_ok'] = syntax.returncode == 0
    result['checks']['sdf_syntax_output'] = (syntax.stdout + syntax.stderr).strip()[:2000]

    server = run(f'ign gazebo -v 3 -s -r --iterations 400 {WORLD}', 180)
    log = server.stdout + server.stderr
    errors = [line.strip() for line in log.splitlines() if '[Err]' in line]
    result['checks']['server_exit_code'] = server.returncode
    result['checks']['gazebo_error_count'] = len(errors)
    result['checks']['gazebo_errors'] = errors[:10]
    result['checks']['mesh_missing'] = 'Unable to find file' in log
    result['checks']['sim_time_reached'] = bool(re.search(r'Sim time.*?\[', log))

    models, gz_errors = [], []
    listing = run(f'ign model --list 2>&1', 60)
    result['checks']['model_list_raw'] = (listing.stdout + listing.stderr).strip()[:400]

    report = Path('/mnt/d/rob-memory/outputs/lab_nav_20261105/load_check.json')
    ok = (result['checks']['sdf_syntax_ok']
          and result['checks']['gazebo_error_count'] == 0
          and not result['checks']['mesh_missing'])
    result['ok'] = ok
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
