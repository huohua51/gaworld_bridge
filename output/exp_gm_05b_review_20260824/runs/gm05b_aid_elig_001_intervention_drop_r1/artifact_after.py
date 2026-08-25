"""Check if a person is eligible based on age and income.

This module provides a function to determine if a person meets the eligibility criteria
based on their age and income. The criteria are defined as age being 18 or above and
income being 50,000 or below.

"""

SPEC_VERSION = "v1"
MIN_AGE = 18
INCOME_CAP = 50000

def eligible(age, income):
    return int(age) >= MIN_AGE and int(income) <= INCOME_CAP

if __name__ == "__main__":
    # Example usage of the eligible function
    print(eligible(25, 40000))  # Should return True
    print(eligible(17, 60000))  # Should return False
