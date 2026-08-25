"""
Calculate the minimum return based on the principal amount.
"""

SPEC_VERSION = "v1"
APPLIED_PATCH_IDS = ["patch-01"]

MIN_RETURN_RATE = 0.3

def min_return(principal):
    """
    Calculate the minimum return as 30% of the principal, rounded down to the nearest integer.
    
    :param principal: The principal amount.
    :return: The minimum return as an integer.
    """
    return int(principal * MIN_RETURN_RATE)

if __name__ == "__main__":
    # Example usage
    principal = 1000
    print(min_return(principal))
