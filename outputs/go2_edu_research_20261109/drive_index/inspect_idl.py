from unitree_sdk2py.idl.unitree_go.msg.dds_ import (
    LowState_,
    SportModeState_,
    IMUState_,
    MotorState_,
    BmsState_,
)
import dataclasses

for cls in [LowState_, SportModeState_, IMUState_, MotorState_, BmsState_]:
    print("==", cls.__name__)
    try:
        print([f.name for f in dataclasses.fields(cls)])
    except Exception as e:
        print("err", e, getattr(cls, "__annotations__", None))
