def _minimize_neldermead(func, x0, args=(), callback=None,
                         maxiter=None, maxfev=None, disp=False,
                         return_all=False, initial_simplex=None,
                         xatol=1e-4, fatol=1e-4, adaptive=False,
                         **unknown_options):
    """
    Minimization of scalar function of one or more variables using the
    Nelder-Mead algorithm.

    Options
    -------
    disp : bool
        Set to True to print convergence messages.
    maxiter, maxfev : int
        Maximum allowed number of iterations and function evaluations.
        Will default to ``N*200``, where ``N`` is the number of
        variables, if neither `maxiter` or `maxfev` is set. If both
        `maxiter` and `maxfev` are set, minimization will stop at the
        first reached.
    initial_simplex : array_like of shape (N + 1, N)
        Initial simplex. If given, overrides `x0`.
        ``initial_simplex[j,:]`` should contain the coordinates of
        the j-th vertex of the ``N+1`` vertices in the simplex, where
        ``N`` is the dimension.
    xatol : float, optional
        Absolute error in xopt between iterations that is acceptable for
        convergence.
    fatol : number, optional
        Absolute error in func(xopt) between iterations that is acceptable for
        convergence.
    adaptive : bool, optional
        Adapt algorithm parameters to dimensionality of problem. Useful for
        high-dimensional minimization [1]_.

    References
    ----------
    .. [1] Gao, F. and Han, L.
       Implementing the Nelder-Mead simplex algorithm with adaptive
       parameters. 2012. Computational Optimization and Applications.
       51:1, pp. 259-277

    """
    if 'ftol' in unknown_options:
        warnings.warn("ftol is deprecated for Nelder-Mead,"
                      " use fatol instead. If you specified both, only"
                      " fatol is used.",
                      DeprecationWarning)
        if (np.isclose(fatol, 1e-4) and
                not np.isclose(unknown_options['ftol'], 1e-4)):
            # only ftol was probably specified, use it.
            fatol = unknown_options['ftol']
        unknown_options.pop('ftol')
    if 'xtol' in unknown_options:
        warnings.warn("xtol is deprecated for Nelder-Mead,"
                      " use xatol instead. If you specified both, only"
                      " xatol is used.",
                      DeprecationWarning)
        if (np.isclose(xatol, 1e-4) and
                not np.isclose(unknown_options['xtol'], 1e-4)):
            # only xtol was probably specified, use it.
            xatol = unknown_options['xtol']
        unknown_options.pop('xtol')

    _check_unknown_options(unknown_options)
    maxfun = maxfev
    retall = return_all

    fcalls, func = wrap_function(func, args)

    if adaptive:
        dim = float(len(x0))
        rho = 1
        chi = 1 + 2/dim
        psi = 0.75 - 1/(2*dim)
        sigma = 1 - 1/dim
    else:
        rho = 1
        chi = 2
        psi = 0.5
        sigma = 0.5

    nonzdelt = 0.05
    zdelt = 0.00025

    x0 = asfarray(x0).flatten()

    if initial_simplex is None:
        N = len(x0)

        sim = numpy.zeros((N + 1, N), dtype=x0.dtype)
        sim[0] = x0
        for k in range(N):
            y = numpy.array(x0, copy=True)
            if y[k] != 0:
                y[k] = (1 + nonzdelt)*y[k]
            else:
                y[k] = zdelt
            sim[k + 1] = y
    else:
        sim = np.asfarray(initial_simplex).copy()
        if sim.ndim != 2 or sim.shape[0] != sim.shape[1] + 1:
            raise ValueError("`initial_simplex` should be an array of shape (N+1,N)")
        if len(x0) != sim.shape[1]:
            raise ValueError("Size of `initial_simplex` is not consistent with `x0`")
        N = sim.shape[1]

    if retall:
        allvecs = [sim[0]]

    # If neither are set, then set both to default
    if maxiter is None and maxfun is None:
        maxiter = N * 200
        maxfun = N * 200
    elif maxiter is None:
        # Convert remaining Nones, to np.inf, unless the other is np.inf, in
        # which case use the default to avoid unbounded iteration
        if maxfun == np.inf:
            maxiter = N * 200
        else:
            maxiter = np.inf
    elif maxfun is None:
        if maxiter == np.inf:
            maxfun = N * 200
        else:
            maxfun = np.inf

    one2np1 = list(range(1, N + 1))
    fsim = numpy.zeros((N + 1,), float)

    for k in range(N + 1):
        fsim[k] = func(sim[k])

    ind = numpy.argsort(fsim)
    fsim = numpy.take(fsim, ind, 0)
    # sort so sim[0,:] has the lowest function value
    sim = numpy.take(sim, ind, 0)

    iterations = 1

    while (fcalls[0] < maxfun and iterations < maxiter):
        if (numpy.max(numpy.ravel(numpy.abs(sim[1:] - sim[0]))) <= xatol and
                numpy.max(numpy.abs(fsim[0] - fsim[1:])) <= fatol):
            break

        xbar = numpy.add.reduce(sim[:-1], 0) / N
        xr = (1 + rho) * xbar - rho * sim[-1]
        fxr = func(xr)
        doshrink = 0

        if fxr < fsim[0]:
            xe = (1 + rho * chi) * xbar - rho * chi * sim[-1]
            fxe = func(xe)

            if fxe < fxr:
                sim[-1] = xe
                fsim[-1] = fxe
            else:
                sim[-1] = xr
                fsim[-1] = fxr
        else:  # fsim[0] <= fxr
            if fxr < fsim[-2]:
                sim[-1] = xr
                fsim[-1] = fxr
            else:  # fxr >= fsim[-2]
                # Perform contraction
                if fxr < fsim[-1]:
                    xc = (1 + psi * rho) * xbar - psi * rho * sim[-1]
                    fxc = func(xc)

                    if fxc <= fxr:
                        sim[-1] = xc
                        fsim[-1] = fxc
                    else:
                        doshrink = 1
                else:
                    # Perform an inside contraction
                    xcc = (1 - psi) * xbar + psi * sim[-1]
                    fxcc = func(xcc)

                    if fxcc < fsim[-1]:
                        sim[-1] = xcc
                        fsim[-1] = fxcc
                    else:
                        doshrink = 1

                if doshrink:
                    for j in one2np1:
                        sim[j] = sim[0] + sigma * (sim[j] - sim[0])
                        fsim[j] = func(sim[j])

        ind = numpy.argsort(fsim)
        sim = numpy.take(sim, ind, 0)
        fsim = numpy.take(fsim, ind, 0)
        if callback is not None:
            callback(sim[0])
        iterations += 1
        if retall:
            allvecs.append(sim[0])

    x = sim[0]
    fval = numpy.min(fsim)
    warnflag = 0

    if fcalls[0] >= maxfun:
        warnflag = 1
        msg = _status_message['maxfev']
        if disp:
            print('Warning: ' + msg)
    elif iterations >= maxiter:
        warnflag = 2
        msg = _status_message['maxiter']
        if disp:
            print('Warning: ' + msg)
    else:
        msg = _status_message['success']
        if disp:
            print(msg)
            print("         Current function value: %f" % fval)
            print("         Iterations: %d" % iterations)
            print("         Function evaluations: %d" % fcalls[0])

    result = OptimizeResult(fun=fval, nit=iterations, nfev=fcalls[0],
                            status=warnflag, success=(warnflag == 0),
                            message=msg, x=x, final_simplex=(sim, fsim))
    if retall:
        result['allvecs'] = allvecs
    return result