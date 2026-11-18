import xml.etree.ElementTree as ET
p='/mnt/d/rob-memory/sim/experiments/agentvln_hunter/scenes/lab_agentvln_world.sdf'
root=ET.parse(p).getroot()
world=root.find('world')
print('root', root.tag, 'world', world.attrib)
for child in list(world):
    if child.tag in ('model','include'):
        print('WORLD CHILD', child.tag, child.attrib.get('name'), 'pose', (child.findtext('pose') or '').strip())
    elif child.tag=='plugin':
        print('WORLD PLUGIN', child.attrib.get('name'))
veh=[m for m in world.findall('model') if m.attrib.get('name')=='hz_hunter_full']
if veh:
    print('vehicle children tags', [(c.tag,c.attrib.get('name')) for c in list(veh[0])])
