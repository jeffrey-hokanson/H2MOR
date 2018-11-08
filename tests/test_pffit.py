import numpy as np
from mor import PartialFractionRationalFit
from mor.check_der import check_jacobian

 
def pf_check_jacobian_complex(z, f, W,  m = 5, n = 6):
	pf = PartialFractionRationalFit(m, n, field = 'complex')
	pf.z = z
	pf.f = f
	pf.W = W
	pf._set_scaling()
	lam = np.random.randn(n) + 1j*np.random.randn(n)
	
	res = lambda lam: pf.residual(lam.view(complex), return_real=True)
	jac = lambda lam: pf.jacobian(lam.view(complex))

	return check_jacobian(lam.view(float), res, jac)

def pf_check_jacobian_complex_plain(z, f, W,  m = 5, n = 6):
	pf = PartialFractionRationalFit(m, n, field = 'complex')
	pf.z = z
	pf.f = f
	pf.W = W
	pf._set_scaling()
	
	lam = np.random.randn(n) + 1j*np.random.randn(n)
	rho_c = np.random.randn(n+(m-n+1)) + 1j*np.random.randn(n+(m-n+1))
	x = np.hstack([lam, rho_c])
	
	res = lambda x: pf.plain_residual(x.view(complex), return_real = True)
	jac = lambda x: pf.plain_jacobian(x.view(complex))

	return check_jacobian(x.view(float), res, jac)

def pf_check_jacobian_real(z, f, W,  m = 5, n = 6):
	pf = PartialFractionRationalFit(m, n, field = 'complex')
	pf.z = z
	pf.f = f
	pf.W = W
	pf._set_scaling()
	lam = np.random.randn(n) + 1j*np.random.randn(n)
	b = pf._lam2b(lam)
	
	res = lambda b: pf.residual_real(b, return_real=True)
	jac = lambda b: pf.jacobian_real(b)

	return check_jacobian(b, res, jac)


def test_pf_jacobian_tan():
	# Generate test data
	N = 100
	coeff = 4
	z = np.exp(2j*np.pi*np.linspace(0,1, N, endpoint = False))
	f = np.tan(coeff*z)
	
	W1 = lambda x : x
	W2a = np.random.randn(N,N) + 1j * np.random.randn(N,N)
	W2 = lambda x: np.dot(W2a, x)
	
	# Check for different orders
	for (m,n) in [(5,6), (7,6)]:
		# unweighted / weighted check
		for W in [W1, W2]:
			assert pf_check_jacobian_complex(z, f, W, m, n) < 1e-7
			assert pf_check_jacobian_real(z, f, W, m, n) < 1e-7
			assert pf_check_jacobian_complex_plain(z, f, W, m, n) < 1e-7


