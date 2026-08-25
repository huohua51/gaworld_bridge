SPEC_VERSION = "v1"
QUEUE_CAP = 50

def can_join(length):
    return length < QUEUE_CAP
