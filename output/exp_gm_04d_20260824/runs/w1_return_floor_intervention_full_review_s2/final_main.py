"""
This module provides a function to calculate the minimum return based on the principal amount.
"""

SPEC_VERSION = "v2"
APPLIED_PATCH_IDS = ["patch-01"]

MIN_RETURN_RATE = 0.5

def min_return(principal):
    """
    Calculate the minimum return based on the principal amount.

    :param principal: The principal amount for which the minimum return is to be calculated.
    :return: The minimum return as an integer.
    """
    return int(principal * MIN_RETURN_RATE)

if __name__ == "__main__":
    # Example usage
    principal = 1000
    print(min_return(principal))
