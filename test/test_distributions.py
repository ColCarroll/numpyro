from functools import reduce
from operator import mul

import numpy as onp
import pytest
import scipy.stats as osp_stats
from numpy.testing import assert_allclose

import jax
import jax.numpy as np
import jax.random as random
from jax import grad, lax
from jax.scipy.special import logit

import numpyro.distributions as dist


@pytest.mark.parametrize('jax_dist', [
    dist.beta,
    dist.cauchy,
    dist.expon,
    dist.gamma,
    dist.lognorm,
    dist.norm,
    dist.t,
    dist.uniform,
], ids=lambda jax_dist: jax_dist.name)
@pytest.mark.parametrize('loc, scale', [
    (1, 1),
    (1., np.array([1., 2.])),
])
@pytest.mark.parametrize('prepend_shape', [
    None,
    (),
    (2,),
    (2, 3),
])
def test_continuous_shape(jax_dist, loc, scale, prepend_shape):
    rng = random.PRNGKey(0)
    args = (1,) * jax_dist.numargs
    expected_shape = lax.broadcast_shapes(*[np.shape(loc), np.shape(scale)])
    samples = jax_dist.rvs(*args, loc=loc, scale=scale, random_state=rng)
    assert isinstance(samples, jax.interpreters.xla.DeviceArray)
    assert np.shape(samples) == expected_shape
    assert np.shape(jax_dist(*args, loc=loc, scale=scale).rvs(random_state=rng)) == expected_shape
    if prepend_shape is not None:
        expected_shape = prepend_shape + lax.broadcast_shapes(*[np.shape(loc), np.shape(scale)])
        assert np.shape(jax_dist.rvs(*args, loc=loc, scale=scale,
                                     size=expected_shape, random_state=rng)) == expected_shape
        assert np.shape(jax_dist(*args, loc=loc, scale=scale)
                        .rvs(random_state=rng, size=expected_shape)) == expected_shape


def idfn(param):
    if isinstance(param, (osp_stats._distn_infrastructure.rv_generic,
                          osp_stats._multivariate.multi_rv_generic)):
        return param.name
    return repr(param)


@pytest.mark.parametrize('jax_dist, dist_args', [
    (dist.dirichlet, (np.ones(3),)),
    (dist.dirichlet, (np.ones((2, 3)),)),
], ids=idfn)
@pytest.mark.parametrize('prepend_shape', [
    None,
    (),
    (2,),
    (2, 3),
])
def test_mvcontinuous_shape(jax_dist, dist_args, prepend_shape):
    rng = random.PRNGKey(0)
    expected_shape = lax.broadcast_shapes(*[np.shape(arg) for arg in dist_args])
    samples = jax_dist.rvs(*dist_args, random_state=rng)
    assert isinstance(samples, jax.interpreters.xla.DeviceArray)
    assert np.shape(samples) == expected_shape
    assert np.shape(jax_dist(*dist_args).rvs(random_state=rng)) == expected_shape
    if prepend_shape is not None:
        expected_shape = prepend_shape + lax.broadcast_shapes(*[np.shape(arg) for arg in dist_args])
        samples = jax_dist.rvs(*dist_args, size=expected_shape[:-1], random_state=rng)
        assert np.shape(samples) == expected_shape
        samples = jax_dist(*dist_args).rvs(random_state=rng, size=expected_shape[:-1])
        assert np.shape(samples) == expected_shape


@pytest.mark.parametrize('jax_dist, dist_args', [
    (dist.bernoulli, (0.1,)),
    (dist.bernoulli, (np.array([0.3, 0.5]),)),
    (dist.binom, (10, 0.4)),
    (dist.binom, (np.array([10]), np.array([0.4, 0.3]))),
    (dist.multinomial, (10, np.array([0.1, 0.4, 0.5]))),
    (dist.multinomial, (10, np.array([1.]))),
], ids=idfn)
@pytest.mark.parametrize('prepend_shape', [
    None,
    (),
    (2,),
    (2, 3),
])
def test_discrete_shape(jax_dist, dist_args, prepend_shape):
    rng = random.PRNGKey(0)
    sp_dist = getattr(osp_stats, jax_dist.name)
    expected_shape = np.shape(sp_dist.rvs(*dist_args))
    samples = jax_dist.rvs(*dist_args, random_state=rng)
    assert isinstance(samples, jax.interpreters.xla.DeviceArray)
    assert np.shape(samples) == expected_shape
    if prepend_shape is not None:
        shape = prepend_shape + lax.broadcast_shapes(*[np.shape(arg) for arg in dist_args])
        expected_shape = np.shape(sp_dist.rvs(*dist_args, size=shape))
        assert np.shape(jax_dist.rvs(*dist_args, size=shape, random_state=rng)) == expected_shape


@pytest.mark.parametrize('jax_dist', [
    dist.beta,
    dist.cauchy,
    dist.expon,
    dist.gamma,
    dist.lognorm,
    dist.norm,
    dist.t,
    dist.uniform,
], ids=lambda jax_dist: jax_dist.name)
@pytest.mark.parametrize('loc, scale', [
    (1., 1.),
    (1., np.array([1., 2.])),
])
def test_sample_gradient(jax_dist, loc, scale):
    rng = random.PRNGKey(0)
    args = (1,) * jax_dist.numargs
    expected_shape = lax.broadcast_shapes(*[np.shape(loc), np.shape(scale)])

    def fn(args, loc, scale):
        return jax_dist.rvs(*args, loc=loc, scale=scale, random_state=rng).sum()

    # FIXME: find a proper test for gradients of arg parameters
    assert len(grad(fn)(args, loc, scale)) == jax_dist.numargs
    assert_allclose(grad(fn, 1)(args, loc, scale),
                    loc * reduce(mul, expected_shape[:len(expected_shape) - np.ndim(loc)], 1.))
    assert_allclose(grad(fn, 2)(args, loc, scale),
                    jax_dist.rvs(*args, size=expected_shape, random_state=rng))


@pytest.mark.parametrize('jax_dist, dist_args', [
    (dist.dirichlet, (np.ones(3),)),
    (dist.dirichlet, (np.ones((2, 3)),)),
], ids=idfn)
def test_mvsample_gradient(jax_dist, dist_args):
    rng = random.PRNGKey(0)

    def fn(args):
        return jax_dist.rvs(*args, random_state=rng).sum()

    # FIXME: find a proper test for gradients of arg parameters
    assert len(grad(fn)(dist_args)) == jax_dist.numargs


@pytest.mark.parametrize('jax_dist', [
    dist.beta,
    dist.cauchy,
    dist.expon,
    dist.gamma,
    dist.lognorm,
    dist.norm,
    dist.t,
    dist.uniform,
], ids=lambda jax_dist: jax_dist.name)
@pytest.mark.parametrize('loc_scale', [
    (),
    (1,),
    (1, 1),
    (1., np.array([1., 2.])),
])
def test_continuous_logpdf(jax_dist, loc_scale):
    rng = random.PRNGKey(0)
    args = (1,) * jax_dist.numargs + loc_scale
    samples = jax_dist.rvs(*args, random_state=rng)
    sp_dist = getattr(osp_stats, jax_dist.name)
    assert_allclose(jax_dist.logpdf(samples, *args), sp_dist.logpdf(samples, *args), atol=1e-6)


@pytest.mark.parametrize('jax_dist, dist_args', [
    (dist.dirichlet, (np.array([1., 2., 3.]),)),
], ids=idfn)
@pytest.mark.parametrize('shape', [
    None,
    (),
    (2,),
    (2, 3),
])
def test_mvcontinuous_logpdf(jax_dist, dist_args, shape):
    rng = random.PRNGKey(0)
    samples = jax_dist.rvs(*dist_args, size=shape, random_state=rng)
    sp_dist = getattr(osp_stats, jax_dist.name)
    # XXX scipy.stats.dirichlet does not work with batch
    if samples.ndim == 1:
        assert_allclose(jax_dist.logpdf(samples, *dist_args),
                        sp_dist.logpdf(samples, *dist_args), atol=1e-6)

    assert jax_dist.logpdf(samples, *dist_args).shape == samples.shape[:-1]


@pytest.mark.parametrize('jax_dist, dist_args', [
    (dist.bernoulli, (0.1,)),
    (dist.bernoulli, (np.array([0.3, 0.5]),)),
    (dist.binom, (10, 0.4)),
    (dist.binom, (np.array([10]), np.array([0.4, 0.3]))),
    (dist.binom, [np.array([2, 5]), np.array([[0.4], [0.5]])]),
    (dist.multinomial, (10, np.array([0.1, 0.4, 0.5]))),
    (dist.multinomial, (10, np.array([1.]))),
], ids=idfn)
@pytest.mark.parametrize('shape', [
    None,
    (),
    (2,),
    (2, 3),
])
def test_discrete_logpmf(jax_dist, dist_args, shape):
    rng = random.PRNGKey(0)
    sp_dist = getattr(osp_stats, jax_dist.name)
    samples = jax_dist.rvs(*dist_args, random_state=rng)
    assert_allclose(jax_dist.logpmf(samples, *dist_args),
                    sp_dist.logpmf(onp.asarray(samples), *dist_args),
                    rtol=1e-5)
    if shape is not None:
        shape = shape + lax.broadcast_shapes(*[np.shape(arg) for arg in dist_args])
        samples = jax_dist.rvs(*dist_args, size=shape, random_state=rng)
        assert_allclose(jax_dist.logpmf(samples, *dist_args),
                        sp_dist.logpmf(onp.asarray(samples), *dist_args),
                        rtol=1e-5)

        def fn(sample, *args):
            return np.sum(jax_dist.logpmf(sample, *args))

        for i in range(len(dist_args)):
            logpmf_grad = grad(fn, i + 1)(samples, *dist_args)
            assert np.all(np.isfinite(logpmf_grad))


@pytest.mark.parametrize('jax_dist, dist_args', [
    (dist.bernoulli, (0.1,)),
    (dist.bernoulli, (np.array([0.3, 0.5]),)),
    (dist.binom, (10, 0.4)),
    (dist.binom, (np.array([10]), np.array([0.4, 0.3]))),
    (dist.binom, (np.array([2, 5]), np.array([[0.4], [0.5]]))),
    (dist.multinomial, (10, np.array([0.1, 0.4, 0.5]))),
    (dist.multinomial, (10, np.array([1., 1.]))),
], ids=idfn)
def test_discrete_logpmf_args_check(jax_dist, dist_args):
    sample = jax_dist.rvs(*dist_args, random_state=random.PRNGKey(0))
    with pytest.raises(ValueError, match='Invalid distribution arguments'):
        dist_args_invalid = dist_args[:-1] + (dist_args[-1] + 1.,)
        jax_dist.logpmf(sample, *dist_args_invalid)
    with pytest.raises(ValueError, match='Invalid values'):
        sample_oos = sample - 0.5
        jax_dist.logpmf(sample_oos, *dist_args)


@pytest.mark.parametrize('jax_dist, dist_args', [
    (dist.bernoulli, (0.1,)),
    (dist.bernoulli, (np.array([0.3, 0.5]),)),
], ids=idfn)
def test_discrete_with_logits(jax_dist, dist_args):
    rng = random.PRNGKey(0)
    logit_args = dist_args[:-1] + (logit(dist_args[-1]),)

    actual_sample = jax_dist.rvs(*dist_args, random_state=rng)
    expected_sample = jax_dist(*logit_args, is_logits=True).rvs(random_state=rng)
    assert_allclose(actual_sample, expected_sample)

    actual_pmf = jax_dist.logpmf(actual_sample, *dist_args)
    expected_pmf = jax_dist(*logit_args, is_logits=True).logpmf(actual_sample)
    assert_allclose(actual_pmf, expected_pmf, rtol=1e-6)
