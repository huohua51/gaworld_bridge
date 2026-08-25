SPEC_VERSION = "v1"
REDEEM_MIN = 200

def can_redeem(points):
    return points >= REDEEM_MIN
