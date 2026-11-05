"""Reassess retained raw experiment telemetry; never rewrite original trial records."""
import csv
import json
from pathlib import Path
from run import ROOT,OUT,assess

rows=[]
for path in sorted((OUT/'motion_trials').glob('*/result.json')):
    record=json.loads(path.read_text(encoding='utf-8'))
    raw=path.parent/'transport.jsonl'
    if not raw.exists():continue
    telemetry=[json.loads(line) for line in raw.read_text().splitlines() if line.strip()]
    if record.get('state')!='completed':continue
    metrics=assess(telemetry,record['profile'])
    if record.get('sensors_enabled'):
        metrics['checks']['native_sensors_during_motion']=bool(record.get('native_sensors',{}).get('ok'))
        metrics['passed']=all(metrics['checks'].values())
    angular=.08 if record['profile']=='left' else (-.08 if record['profile']=='right' else 0)
    rows.append({'run':path.parent.name,'profile':record['profile'],'raw_record_passed':record.get('result',{}).get('passed'),
                 'assessment_v2':metrics,'fixed_profile_angular_command_rad_s':angular,
                 'legacy_metadata_angular_field_differs':record.get('angular_velocity_rad_s')!=angular,
                 'owned_server_stopped':record.get('owned_server_stopped'),
                 'owned_process_groups_closed':record.get('owned_process_groups_closed'),
                 'result_file':str(path.relative_to(ROOT))})
summary={'assessment_version':2,'trials':rows,
         'audit_notes':['Original trials and telemetry are retained, including the first collision result marked failed.',
                        'That collision criterion incorrectly required passive front wheels to keep rotating against a barrier; v2 checks body stopping/nonpenetration and records wheel slip instead.',
                        'Early collision/full_straight metadata mistakenly listed -0.08 rad/s although their fixed transport profiles commanded zero; corrected metadata are separated from original records.',
                        'Turn tests demonstrate direction/inner-outer steering and odometry consistency; they do not establish exact angular-command tracking or calibrated dynamics.']}
(OUT/'motion_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'motion_metrics.csv').open('w',newline='') as f:
    writer=csv.writer(f);writer.writerow(['run','profile','original_pass','assessment_v2_pass','forward_m','lateral_m','truth_yaw_rad','odom_yaw_rad','odom_distance_m','stop_speed_m_s'])
    for row in rows:
        m=row['assessment_v2'];writer.writerow([row['run'],row['profile'],row['raw_record_passed'],m['passed'],m['forward_m'],m['lateral_m'],m['yaw_change_rad'],m['odom_yaw_change_rad'],m['odom_distance_m'],m['final_odom_speed_m_s']])
print(json.dumps({'trials':len(rows),'current_criteria_passed':sum(r['assessment_v2']['passed'] for r in rows),'original_failed_trials_preserved':sum(r['raw_record_passed'] is False for r in rows)}))
