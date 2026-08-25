SPEC_VERSION = "v1"
MAX_HOURS = 40


def can_work(certified, hours):
    return bool(certified) and int(hours) <= MAX_HOURS
