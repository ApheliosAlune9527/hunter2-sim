import importlib
for m in ('matplotlib','PIL','numpy','cv2'):
    try:
        mod=importlib.import_module(m); print(m, getattr(mod,'__version__','ok'))
    except Exception as e:
        print(m, 'missing', e)
