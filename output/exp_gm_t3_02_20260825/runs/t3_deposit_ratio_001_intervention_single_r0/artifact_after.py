SPEC_VERSION = "v1"
DEPOSIT_PERCENT = 30

def deposit(price):
    return price * DEPOSIT_PERCENT // 100
