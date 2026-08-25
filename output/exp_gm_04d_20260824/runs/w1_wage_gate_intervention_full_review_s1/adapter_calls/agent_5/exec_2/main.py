"""decide function to compare take_home salary with a fixed threshold"""

SPEC_VERSION = "v2"
APPLIED_PATCH_IDS = ["patch-01"]

THRESHOLD = 70000

def decide(take_home):
    """Decide whether to accept a job offer based on take_home salary compared to a fixed threshold."""
    return "accept" if take_home >= THRESHOLD else "reject"

if __name__ == "__main__":
    # Example usage
    print(decide(65000))  # Output: accept
    print(decide(60000))  # Output: reject
