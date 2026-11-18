
import json
from pathlib import Path
lay = json.loads(Path('/mnt/d/rob-memory/sim/experiments/agentvln_hunter/config/target_layout_straight.json').read_text())
print('world:', lay.get('world'))
print('boxes:', [(b['name'], b['x'], b['y'], b['size']) for b in lay['blue_boxes']])
print('obs:', lay.get('observation_pose'), 'dock:', lay.get('expected_dock'), 'zone:', lay.get('parking_zone'))
print('instruction:', lay.get('instruction'), '| scope:', json.dumps(lay.get('validation_scope'), ensure_ascii=False)[:200])
