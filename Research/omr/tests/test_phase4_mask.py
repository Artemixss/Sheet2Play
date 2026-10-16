import pytest
from phase4_mask import valid_steps


def test_partial_last_step_remains_valid():
    assert valid_steps(321, 16) == 21
    assert valid_steps(320, 16) == 20


@pytest.mark.parametrize("width,timestep", [(0, 16), (12, 0), (True, 16), (12.5, 16)])
def test_invalid_lengths_fail(width, timestep):
    with pytest.raises(ValueError):
        valid_steps(width, timestep)
