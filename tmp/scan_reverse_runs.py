import json, glob, os

for pat in ('agentvln_reverse_record_*', 'agentvln_reverse_dock_*'):
    for d in sorted(glob.glob(r'D:\rob-memory\outputs\%s' % pat)):
        rp = os.path.join(d, 'report.json')
        name = os.path.basename(d)
        if not os.path.exists(rp):
            print('%s: NO report.json' % name)
            continue
        try:
            d0 = json.load(open(rp, encoding='utf-8'))
        except Exception as e:
            print('%s: unreadable %s' % (name, e))
            continue
        ok = d0.get('pass')
        chk = d0.get('checks') or {}
        fails = [k for k, v in chk.items() if v is False] if isinstance(chk, dict) else []
        ev = d0.get('evaluation') or {}
        lat = ev.get('lateral_error_m')
        head = ev.get('heading_error_rad')
        gap = ev.get('front_gap_m')
        print('%s: pass=%s fails=%s lat=%s head=%s gap=%s' % (name, ok, fails, lat, head, gap))
