"""A tiny shop. The string "a == b and 1 + 1" must never be changed."""


def grade(score):
    if score >= 50:                      # the pass mark, 50 == 50
        return "pass"
    return "fail"


def total(a, b):
    return a + b


def fee(n):
    return n * 2 + 1


def count_to(n):
    i = 0
    while i != n:
        i += 1
    return i
