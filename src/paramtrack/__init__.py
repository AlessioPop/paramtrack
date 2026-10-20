import ast
import builtins
import inspect
from collections import ChainMap
from functools import cache, wraps
from html import escape

__all__ = ["track_class", "track_function"]

VAR_KEYWORD = inspect.Parameter.VAR_KEYWORD


# "name = value" lines with the "=" signs lined up, drawn as a tree.
def tree(arguments):
    width = max(map(len, arguments), default=0)
    lines = [f"{k:<{width}} = {v}" for k, v in arguments.items()]
    return [f"├─ {line}" for line in lines[:-1]] + [f"└─ {line}" for line in lines[-1:]]


# Stands in for an argument without a default until a call gives it a value.
class Unset:
    def __repr__(self):
        return "?"


UNSET = Unset()


class Parameters(dict):
    def __init__(self):
        super().__init__()
        self.uncalled = {}  # functions not called yet, as name -> function giving their defaults

    # Recompute the entries of functions not called yet: what their **kwargs are passed on to
    # may have been defined after them.
    def refresh(self):
        for name, defaults in self.uncalled.items():
            self[name] = defaults()

    # Text version, used by print() and the terminal.
    def __repr__(self):
        self.refresh()
        blocks = []
        for name, arguments in self.items():
            blocks.append("\n".join([f"\033[1m{name}\033[0m", *tree(arguments)]))  # \033[1m = bold
        return "\n\n".join(blocks)

    # Clickable version, used by Jupyter; click a method name to unfold it.
    def _repr_html_(self):
        self.refresh()
        html = ""
        for name, arguments in self.items():
            lines = escape("\n".join(tree(arguments)))
            html += f"<details><summary><b>{name}</b></summary><pre style='margin: 0 0 0 1.2em'>{lines}</pre></details>"
        return html


# The calls in func's source that pass its **kwargs on, e.g. orbit_fit(data=path, **params),
# as (called expression, number of positional arguments, names of the other keywords).
@cache
def forwarding_calls(func):
    kwargs = next((p.name for p in inspect.signature(func).parameters.values() if p.kind is VAR_KEYWORD), None)
    try:
        source = inspect.getsource(func)
        if source[:1].isspace():  # methods are indented, which ast.parse rejects
            source = "if True:\n" + source
        nodes = ast.walk(ast.parse(source))
    except (OSError, TypeError, SyntaxError):  # no source, e.g. typed into a plain python shell
        return []
    calls = []
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        if any(k.arg is None and isinstance(k.value, ast.Name) and k.value.id == kwargs for k in node.keywords):
            calls.append((node.func, len(node.args), {k.arg for k in node.keywords if k.arg}))
    return calls


# Look up what is being called: a name or attribute chain like orbit_fit, module.function or self.method.
def resolve(node, namespace):
    if isinstance(node, ast.Name):
        return namespace[node.id]
    if isinstance(node, ast.Attribute):
        return getattr(resolve(node.value, namespace), node.attr)
    raise LookupError(ast.dump(node))


# The parameters that func's **kwargs end up in: the passed value where given, the default otherwise,
# and UNSET for those without one.
# local holds func's own arguments so that self.method(**kwargs) resolves. Follows chains of **kwargs.
def forwarded(func, local, kwargs, seen=()):
    seen = (*seen, func)
    result = {}
    for node, n_positional, explicit in forwarding_calls(func):
        try:
            namespace = ChainMap(local, inspect.getclosurevars(func).nonlocals, func.__globals__, vars(builtins))
            callee = resolve(node, namespace)
            parameters = list(inspect.signature(callee).parameters.values())
        except Exception:  # can't tell what is called; the passed keywords are still shown below
            continue
        rest = dict(kwargs)
        for i, p in enumerate(parameters):
            if p.kind in (p.VAR_POSITIONAL, VAR_KEYWORD) or p.name in explicit:
                continue
            if i < n_positional and p.kind is not p.KEYWORD_ONLY:  # filled by a positional argument
                continue
            if p.name in rest:
                result.setdefault(p.name, rest.pop(p.name))
            else:
                result.setdefault(p.name, UNSET if p.default is p.empty else p.default)
        inner = inspect.unwrap(getattr(callee, "__func__", callee))
        if parameters and parameters[-1].kind is VAR_KEYWORD and inspect.isfunction(inner) and inner not in seen:
            inner_local = {next(iter(inspect.signature(inner).parameters)): callee.__self__} if inspect.ismethod(callee) else {}
            for name, value in forwarded(inner, inner_local, rest, seen).items():
                result.setdefault(name, value)
    for name, value in kwargs.items():
        result.setdefault(name, value)
    return result


# What is stored for one call: {name: repr(value)}, without self.
def describe(function, signature, arguments):
    result = {}
    for name, value in arguments.items():
        # Instead of one dict, list what **kwargs is passed on to, defaults included.
        if signature.parameters[name].kind is VAR_KEYWORD:
            for key, val in forwarded(inspect.unwrap(function), arguments, value).items():
                result.setdefault(key, val)
        elif name != "self":
            result[name] = value
    return {k: repr(v) for k, v in result.items()}


def track(function, parameters):
    signature = inspect.signature(function)

    @wraps(function)
    def wrapper(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        parameters.uncalled.pop(function.__name__, None)
        parameters[function.__name__] = describe(function, signature, bound.arguments)
        return function(*args, **kwargs)
    return wrapper


def track_class(cls):
    """Track the arguments of every method of a class.

    Each call stores the method's arguments, defaults included, in ``cls.parameters``
    under the method's name, replacing those of the previous call. Keywords that a
    method passes on with ``**kwargs`` are listed together with the parameters and
    defaults of the function receiving them.

    Parameters
    ----------
    cls : type
        The class to track.

    Returns
    -------
    type
        The same class, with its methods wrapped and a ``parameters`` attribute added.

    Examples
    --------
    >>> @track_class
    ... class Telescope:
    ...     def observe(self, target, exposure=30):
    ...         ...
    >>> telescope = Telescope()
    >>> telescope.observe("Vega")
    >>> telescope.parameters["observe"]
    {'target': "'Vega'", 'exposure': '30'}
    """
    cls.parameters = Parameters()
    for name, method in list(vars(cls).items()):
        if inspect.isfunction(method):
            setattr(cls, name, track(method, cls.parameters))
    return cls


def track_function(function):
    """Track the arguments of a function.

    Each call stores the arguments, defaults included, in ``function.parameters``,
    replacing those of the previous call. Before the first call, ``function.parameters``
    shows the defaults, with ``?`` for arguments that have none. Keywords passed on with
    ``**kwargs`` are listed as in :func:`track_class`.

    Parameters
    ----------
    function : callable
        The function to track.

    Returns
    -------
    callable
        A wrapper around the function with a ``parameters`` attribute.

    Examples
    --------
    >>> @track_function
    ... def observe(target, exposure=30):
    ...     ...
    >>> observe.parameters["observe"]
    {'target': '?', 'exposure': '30'}
    >>> observe("Vega")
    >>> observe.parameters["observe"]
    {'target': "'Vega'", 'exposure': '30'}
    """
    parameters = Parameters()
    wrapper = track(function, parameters)
    wrapper.parameters = parameters
    # Before the first call: the defaults, and UNSET for arguments without one.
    signature = inspect.signature(function)
    bound = signature.bind_partial()
    bound.apply_defaults()
    arguments = {name: bound.arguments.get(name, UNSET) for name in signature.parameters}
    parameters.uncalled[function.__name__] = lambda: describe(function, signature, arguments)
    parameters.refresh()
    return wrapper
