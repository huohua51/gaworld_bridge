SPEC_VERSION = "v1"
LIMIT = 35
FALLBACK_LIMIT = 40

def classify(value: int) -> str:
    if value <= LIMIT:
        return "primary"
    if value <= FALLBACK_LIMIT:
        return "fallback"
    return "reject"
