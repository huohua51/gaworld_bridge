SPEC_VERSION = "v1"
MIN_AGE = 18
INCOME_CAP = 50000


def eligible(age, income):
    return int(age) >= MIN_AGE and int(income) <= INCOME_CAP
