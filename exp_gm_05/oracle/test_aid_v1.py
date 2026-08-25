from main import allocate, eligible


def test_v1_cap_inclusive():
    assert eligible({"id": "a", "age": 30, "income": 50000, "proof": True, "priority": "standard", "request": 100}) is True


def test_v1_cap_exclusive():
    assert eligible({"id": "a", "age": 30, "income": 50001, "proof": True, "priority": "standard", "request": 100}) is False


def test_v1_allows_45001():
    assert eligible({"id": "a", "age": 30, "income": 45001, "proof": True, "priority": "standard", "request": 100}) is True


def test_age_and_proof():
    assert eligible({"id": "a", "age": 17, "income": 10000, "proof": True, "priority": "high", "request": 100}) is False
    assert eligible({"id": "a", "age": 30, "income": 10000, "proof": False, "priority": "high", "request": 100}) is False


def test_budget_priority_order():
    people = [
        {"id": "low", "age": 40, "income": 20000, "proof": True, "priority": "standard", "request": 7000},
        {"id": "hi", "age": 40, "income": 20000, "proof": True, "priority": "critical", "request": 7000},
    ]
    grants = {item["id"]: item["granted"] for item in allocate(people)}
    assert grants["hi"] == 7000
    assert grants["low"] == 3000
