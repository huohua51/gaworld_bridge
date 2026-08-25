SPEC_VERSION = "v1"
WEEKDAY_DEADLINE = 30
WEEKEND_DEADLINE = 30

def deadline(weekend: bool) -> int:
    return WEEKEND_DEADLINE if weekend else WEEKDAY_DEADLINE
