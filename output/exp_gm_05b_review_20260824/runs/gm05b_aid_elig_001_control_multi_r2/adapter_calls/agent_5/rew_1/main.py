"""Check if a person is eligible based on age and income.

This module defines a function to determine if a person meets the eligibility criteria
based on their age and income. The criteria are that the age must be 18 or above and
the income must not exceed 50,000.

"""

SPEC_VERSION = "v1"
MIN_AGE = 18
INCOME_CAP = 50000

def eligible(age, income):
    return age >= MIN_AGE and income <= INCOME_CAP

if __name__ == "__main__":
    # Example usage of the eligible function
    print(eligible(25, 40000))  # Should return True
    print(eligible(17, 30000))  # Should return False
    print(eligible(25, 60000))  # Should return False
