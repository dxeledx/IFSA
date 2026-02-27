import numpy as np

from eapp.representation.tangent import sym_to_vec


def test_sym_to_vec_dim():
    c = 7
    a = np.eye(c)
    v = sym_to_vec(a)
    assert v.shape == (c * (c + 1) // 2,)

