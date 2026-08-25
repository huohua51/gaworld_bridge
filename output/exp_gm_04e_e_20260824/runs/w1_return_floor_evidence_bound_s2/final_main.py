"""Calculate the minimum return based on the principal amount."""

SPEC_VERSION = "v1"
APPLIED_PATCH_IDS = "patch-01"
ARTIFACT_SPEC_VERSION = "v1"

RATE = 0.3

def min_return(principal):
    return int(principal * RATE)

if __name__ == "__main__":
    print(min_return(100))
