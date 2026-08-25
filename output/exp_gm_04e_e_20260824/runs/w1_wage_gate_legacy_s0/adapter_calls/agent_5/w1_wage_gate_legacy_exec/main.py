"""decide function to compare take-home salary with a fixed threshold"""

SPEC_VERSION = "v2"
THRESHOLD = 70000

def decide(take_home):
    return "accept" if take_home >= THRESHOLD else "reject"

if __name__ == "__main__":
    # Example usage
    print(decide(65000))  # Output: accept
    print(decide(60000))  # Output: reject
