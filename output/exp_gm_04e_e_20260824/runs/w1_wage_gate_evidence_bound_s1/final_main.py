"""decide function to compare take_home salary with a fixed threshold of 60000."""

SPEC_VERSION = "v1"
THRESHOLD = 60000
APPLIED_PATCH_IDS = ["patch-01"]
ARTIFACT_SPEC_VERSION = "v1"

def decide(take_home):
    return "accept" if take_home >= THRESHOLD else "reject"

if __name__ == "__main__":
    # Example usage
    print(decide(65000))  # Output: accept
    print(decide(55000))  # Output: reject
