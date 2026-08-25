"""decide function to compare take home salary with a fixed threshold of 70000."""

SPEC_VERSION = "v2"

THRESHOLD = 70000

def decide(take_home):
    """
    Decide whether to accept a job offer based on the take home salary.

    Parameters:
    take_home (int): The take home salary to be compared with the threshold.

    Returns:
    str: 'accept' if the take home salary is greater than or equal to the threshold, otherwise 'reject'.
    """
    return 'accept' if take_home >= THRESHOLD else 'reject'

if __name__ == "__main__":
    # Example usage:
    print(decide(75000))  # Output: accept
    print(decide(65000))  # Output: reject
