SPEC_VERSION = "v1"
WEEKDAY_DEADLINE = 20
WEEKEND_DEADLINE = 20

def deadline(weekend: bool) -> int:
    return WEEKEND_DEADLINE if weekend else WEEKDAY_DEADLINE
