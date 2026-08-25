"""decide function to compare take home salary with a fixed reservation wage threshold"""

SPEC_VERSION = "v2"
APPLIED_PATCH_IDS = ["patch-01"]

def decide(take_home):
    RESERVATION_WAGE_THRESHOLD = 70000
    if take_home >= RESERVATION_WAGE_THRESHOLD:
        return "accept"
    else:
        return "reject"

if __name__ == "__main__":
    # Example usage
    print(decide(65000))  # Output: accept
    print(decide(55000))  # Output: reject
