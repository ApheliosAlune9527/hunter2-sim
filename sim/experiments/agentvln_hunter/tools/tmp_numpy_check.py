
import subprocess, sys
code = "import numpy, cv_bridge; print(numpy.__version__, numpy.__file__); print('cv_bridge ok')"
for env_note, extra in (("default", {}), ("PYTHONNOUSERSITE=1", {"PYTHONNOUSERSITE": "1"})):
    import os
    env = dict(os.environ)
    env.update(extra)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    print("==", env_note, "rc", out.returncode)
    print("   ", (out.stdout or out.stderr).strip().splitlines()[:3])
