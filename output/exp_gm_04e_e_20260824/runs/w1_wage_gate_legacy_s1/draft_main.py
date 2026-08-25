SPEC_VERSION = "v1"
THRESHOLD = 60000

def decide(take_home):
    return "accept" if take_home >= THRESHOLD else "reject"
