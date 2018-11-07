import fdcheck as fd
import warnings
import numpy as np
import scipy as sp

class BadStep(Exception):
    pass

def lnsrch_armijo(f, g, p, x0, bt_factor=0.5, ftol=1e-4, maxiter=40, trajectory=None):
    """Back-Tracking Line Search to satify Armijo Condition

        f(x0 + alpha*p) < f(x0) + alpha * ftol * <g,p>

    Parameters
    ----------
    f : callable
        objective function, f: R^n -> R
    g : np.array((n,))
        gradient
    p : np.array((n,))
        descent direction
    x0 : np.array((n,))
        current location
    bt_factor : float [optional] default = 0.5
        backtracking factor
    ftol : float [optional] default = 1e-4
        coefficient in (0,1); see Armijo description in Nocedal & Wright
    maxiter : int [optional] default = 10
        maximum number of iterations of backtrack
    trajectory: function(x0, p, t) [Optional]
        Function that returns next iterate 
    Returns
    -------
    float
        alpha: backtracking coefficient (alpha = 1 implies no backtracking)
    """
    if trajectory is None:
        trajectory = lambda x0, p, t: x0 + t * p
    dg = np.inner(g, p)
    if dg > 0:
        raise Exception('Descent direction p is not a descent direction: p^T g = %g >= 0' % (dg, ))

    alpha = 1

    fx0 = f(x0)
    x = np.copy(x0)
    fx = np.inf
    success = False
    for it in range(maxiter):
        try:
            x = trajectory(x0, p, alpha)
            fx = f(x)
            if fx < fx0 + alpha * ftol * dg:
                success = True
                break
        except BadStep:
            pass
            
        alpha *= bt_factor

    # If we haven't found a good step, stop
    if not success:
        alpha = 0
        x = x0
        fx = fx0
    return x, alpha, fx


def gn(f, F, x0, tol=1e-5, tol_normdx=1e-12, maxiter=100, fdcheck=False, linesearch=None, verbose=0, trajectory=None, gnsolver = None):
    """Gauss-Newton Solver (Dense) via QR Decomp
    
        min_x || f(x) ||
        

    Parameters
    ----------
    f : callable
        residual, f: R^n -> R^m
    F : callable
        Jacobian of residual f, F: R^n -> R^{m x n}
    tol: float [optional] default = 1e-8
        gradient norm stopping criterion
    tol_normdx: float [optional] default = 1e-12
        norm of control update stopping criterion
    maxiter : int [optional] default = 100
        maximum number of iterations of Gauss-Newton
    fdcheck: bool [optional] default = False
        if True, runs a FD check of F and f; warning: can be a costly operation, used for debugging
    linesearch: callable, returns new x
        f : callable, residual, f: R^n -> R^m
        g : gradient, R^n
        p : descent direction, R^n
        x0 : current iterate, R^n
    gnsolver: [optional] callable, returns search direction p 
        Parameters: 
            F: current Jacobian
            f: current residual
        Returns:
            p: search step
            s: singular values of Jacobian
    verbose: int [optional] default = 0
        if >= print convergence history diagnostics

    Returns
    -------
    numpy.array((dof,))
        returns x^* (optimizer)
    int
        info = 0: converged with norm of gradient below tol
        info = 1: norm of gradient did not converge, but ||dx|| below tolerance
        info = 2: did not converge, max iterations exceeded
    """
    n = len(x0)
    if maxiter <= 0: return x0, 4

    if verbose >= 1:
        print('Gauss-Newton Solver Iteration History')
        print('  iter   |   ||f(x)||   |   ||dx||   | cond(F(x)) |    alpha   |  ||grad||  ')
        print('---------|--------------|------------|------------|------------|------------')
    if trajectory is None:
        trajectory = lambda x0, p, t: x0 + t * p

    if linesearch is None:
        linesearch = lnsrch_armijo

    x = x0
    grad = F(x).T.dot(f(x))
    normgrad = np.linalg.norm(grad)

    #rescale tol by norm of initial gradient
    tol = max(tol*normgrad, 1e-14)
    normdx = 1
    for it in range(maxiter):
        residual_increased = False
        if fdcheck == True:
            fd_error = fd.fdcheck(f=f, fp=lambda x, xp: F(x).dot(xp), dof=n, ord=4)
            if fd_error > 1e-6:
                warnings.warn('Gauss-Newton: FD Check Failed, fd_error = %1.2e' % fd_error)
        f_eval = f(x)
        F_eval = F(x)
        
        # Breaks intermetently due to bug in lapack_lite used by Numpy
        # See: numpy/linalg.py line #2038
        #dx, _, rank, s = np.linalg.lstsq(F_eval, -f_eval, rcond = -1)
       
        # Scipy seems to properly check for proper allocation of working space, reporting an error with gelsd
        # so we specify using gelss (an SVD based solver)
        if gnsolver is None:
            dx, _, _, s = sp.linalg.lstsq(F_eval, -f_eval, lapack_driver = 'gelss')
        else:
            dx, s = gnsolver(F_eval, f_eval)

        if not np.all(np.isfinite(dx)):
            print "dx", dx
            print "sing vals", s
            print "F_eval", F_eval.shape, np.all(np.isfinite(F_eval))
            print "f_eval", f_eval.shape, np.all(np.isfinite(f_eval))
            np.savez('breaking_lstsq.npz', A = F_eval, b = -f_eval)
        
        cond = s[0] / s[-1]

        # If Gauss-Newton step is not a descent direction, use -gradient instead
        if np.inner(grad, dx) >= 0:
            dx = -grad

        x_new, alpha, f_eval_new = linesearch(lambda x: np.linalg.norm(f(x)), grad, dx, x, trajectory=trajectory)
        
        if f_eval_new >= np.linalg.norm(f_eval):
            residual_increased = True
        else:
            x = x_new

        normf = np.linalg.norm(f_eval_new)
        normdx = np.linalg.norm(dx)
        grad = F(x).T.dot(f(x))
        normgrad = np.linalg.norm(grad)
        if verbose >= 1:
            print(
                '    %3d  |  %1.4e  |  %1.2e  |  %1.2e  |  %1.2e  |  %1.2e' % (
                it, normf, normdx, cond, alpha, normgrad))
        if normgrad < tol:
            if verbose: print "norm gradient %1.3e less than tolerance %1.3e" % (normgrad, tol)
            break
        if normdx < tol_normdx:
            if verbose: print "norm dx %1.3e less than tolerance %1.3e" % (normdx, tol_normdx)
            break
        if residual_increased:
            if verbose: print "residual increased during line search from %1.5e to %1.5e" % (np.linalg.norm(f_eval), f_eval_new)
            break

    if normgrad <= tol:
        info = 0
        if verbose >= 1:
            print('Gauss-Newton converged successfully!')
    elif normdx <= tol_normdx:
        info = 1
        if verbose >= 1:
            print ('Gauss-Newton did not converge: ||dx|| < tol')
    elif it == maxiter - 1:
        info = 2
        if verbose >= 1:
            print ('Gauss-Newton did not converge: max iterations reached')
    elif f_eval_new >= np.linalg.norm(f_eval):
        info = 3
        if verbose >= 1:
            print ('No progress made during line search')
    else:
        raise Exception('Stopping criteria not determined!')

    return x, info


if __name__ == '__main__':
    # NLS example taken from Wikipedia:
    #   https://en.wikipedia.org/wiki/Gauss-Newton_algorithm#Example
    # Substrate concentration
    s = np.array([0.038, 0.194, 0.425, 0.626, 1.253, 2.500, 3.740])
    # Reaction rate
    r = np.array([0.050, 0.127, 0.094, 0.2122, 0.2729, 0.2665, 0.3317])
    # Rate model
    m = lambda p, s: p[0] * s / (p[1] + s)
    f = lambda p: m(p, s) - r
    F = lambda p: np.c_[s / (p[1] + s), -p[0] * s / (p[1] + s) ** 2]

    x0 = np.zeros((2,))
    x = gn(f, F, x0, fdcheck=True, verbose=1)
