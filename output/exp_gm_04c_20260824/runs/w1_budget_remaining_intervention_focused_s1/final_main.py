"""
This module provides a function to calculate the remaining budget after a certain amount has been spent.
"""

SPEC_VERSION = "v2"

# Constants for the threshold
THRESHOLD = 80

def remaining(spent):
    """
    Calculate the remaining budget after a certain amount has been spent.

    Parameters:
    spent (int): The amount spent.

    Returns:
    int: The remaining budget, ensuring it is not negative.
    """
    return max(0, THRESHOLD - spent)

if __name__ == "__main__":
    # Example usage of the function
    spent_amount = 50
    print(remaining(spent_amount))
