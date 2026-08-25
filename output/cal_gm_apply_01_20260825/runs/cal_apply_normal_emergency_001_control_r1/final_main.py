SPEC_VERSION = "v1"
NORMAL_CAPACITY = 60
EMERGENCY_CAPACITY = 80

def capacity(emergency: bool) -> int:
    return EMERGENCY_CAPACITY if emergency else NORMAL_CAPACITY
