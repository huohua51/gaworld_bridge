"""
Check if a person is eligible based on age and income.
"""

SPEC_VERSION = "v2"

MIN_AGE = 18
INCOME_CAP = 45000

def eligible(age, income):
    return MIN_AGE <= age <= INCOME_CAP and income <= INCOME_CAP

if __name__ == "__main__":
    # Example usage:
    print(eligible(25, 40000))  # Should return True
    print(eligible(17, 30000))  # Should return False
    print(eligible(25, 60000))  # Should return False
