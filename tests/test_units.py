# tests/test_units.py
from engine import ft_in_to_ft
def test_ft_in_to_ft():
    assert ft_in_to_ft("10'6\"") == 10.5
    assert ft_in_to_ft("0") == 0.0
    assert ft_in_to_ft("junk") == 0.0
