"""decide: A function to determine if an offer should be accepted based on the take-home salary."""

SPEC_VERSION = "v2"

# Constants
THRESHOLD = 70000

def decide(take_home):
    """
    Decide whether to accept an offer based on the take-home salary.

    Parameters:
    take_home (int): The take-home salary offered.

    Returns:
    str: 'accept' if the take-home salary is greater than or equal to the threshold, otherwise 'reject'.
    """
    return 'accept' if take_home >= THRESHOLD else 'reject'

if __name__ == "__main__":
    # Example usage
    print(decide(70000))  # Output: accept
    print(decide(69000))  # Output: reject
