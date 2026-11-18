
import sys
sys.path.insert(0, '/mnt/d/rob-memory/sim/experiments/agentvln_reverse_dock')
import parking
face = {'centre': [4.895130979850127, 2.4050975670170462], 'heading': 0.019386665567273902}
print('DOCK_SIDE_SHIFT', parking.DOCK_SIDE_SHIFT)
print('dock', [round(v, 4) for v in parking.dock_from_face(face)])
