import calc


def test_grade():
    assert calc.grade(50) == "pass" and calc.grade(49) == "fail"


def test_total():
    assert calc.total(2, 3) == 5


def test_count():
    assert calc.count_to(3) == 3
