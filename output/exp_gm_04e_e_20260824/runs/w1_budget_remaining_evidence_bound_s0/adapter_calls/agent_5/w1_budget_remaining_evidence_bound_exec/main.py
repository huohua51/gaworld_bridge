"""Calculate the remaining budget after a certain amount has been spent.

This module provides a function to calculate the remaining budget after a
specified amount has been spent. The total budget is fixed at 100.

"""

SPEC_VERSION = "v1"
APPLIED_PATCH_IDS = "patch-01"
ARTIFACT_SPEC_VERSION = "v1"

BUDGET = 100
THRESHOLD = 80

def remaining(spent):
    return max(0, BUDGET - spent)

if __name__ == "__main__":
    print(remaining(THRESHOLD))
