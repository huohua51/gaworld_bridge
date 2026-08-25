"""
Check if a person is eligible based on age and income.
"""

SPEC_VERSION = "1.0"

MIN_AGE = 18
INCOME_CAP = 45000

def eligible(age, income):
    return MIN_AGE <= age <= INCOME_CAP and income <= INCOME_CAP

if __name__ == "__main__":
    # Example usage:
    print(eligible(25, 40000))  # Should return True
    print(eligible(17, 50000))  # Should return False
