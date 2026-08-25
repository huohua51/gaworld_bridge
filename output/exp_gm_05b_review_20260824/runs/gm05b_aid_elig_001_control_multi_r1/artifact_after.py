"""
Check if a person is eligible based on age and income.
"""

SPEC_VERSION = "v1"
MIN_AGE = 18
INCOME_CAP = 50000

def eligible(age, income):
    return age >= MIN_AGE and income <= INCOME_CAP

if __name__ == "__main__":
    # Example usage
    print(eligible(25, 40000))  # Should return True
    print(eligible(17, 60000))  # Should return False
