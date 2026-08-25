"""Calculate the minimum return based on the principal amount.

This module provides a function to calculate the minimum return based on the principal amount.
The minimum return rate is set to 0.5 (50%).

Usage:
    min_return(principal) -> int
        Calculate the minimum return for the given principal amount.

"""

SPEC_VERSION = "v2"
RATE = 0.5

def min_return(principal):
    return int(principal * RATE)

if __name__ == "__main__":
    # Example usage
    principal = 1000
    print(min_return(principal))
