import ast
import builtins
import inspect
import json
from collections import ChainMap
from functools import cache, wraps
from html import escape
from pathlib import Path

__all__ = ["track_class", "track_function"]

VAR_KEYWORD = inspect.Parameter.VAR_KEYWORD


# Stands in for an argument without a default until a call gives it a value.
class Unset:
    def __repr__(self):
        return "?"


UNSET = Unset()


# repr() that can't fail, so that tracking never breaks the call it tracks.
def safe_repr(value):
    try:
        return repr(value)
    except Exception:
        return f"<{type(value).__name__} object>"


# "ValueError: bad prior" for an exception.
def error_text(error):
    try:
        message = str(error)
    except Exception:
        message = ""
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


class Call(dict):
    """The arguments of one call, as ``{name: repr(value)}``.

    Attributes
    ----------
    status : str
        ``"ok"``, ``"failed"``, ``"running"``, or ``"not called"`` for a function tracked
        with :func:`track_function` that hasn't been called yet.
    error : str or None
        The exception of a failed call, e.g. ``"ValueError: bad prior"``.
    sources : dict
        Where each value comes from: ``"passed"`` in the call, the function's own
        ``"default"``, ``"inferred"`` from the function receiving ``**kwargs``, or
        ``"missing"`` for an argument without a value, shown as ``?``.
    inferred_from : dict
        For the values found through ``**kwargs`` that weren't passed: the name of the
        function receiving them.
    """

    def __init__(self, entries, status):
        super().__init__((name, safe_repr(value)) for name, (value, _, _) in entries.items())
        self.sources = {name: source for name, (_, source, _) in entries.items()}
        self.inferred_from = {name: receiver for name, (_, _, receiver) in entries.items() if receiver}
        self.status = status
        self.error = None

    def to_dict(self):
        """The call as plain data that can be saved as JSON.

        Returns
        -------
        dict
            ``{"status": ..., "error": ..., "arguments": {name: {"value": ..., "source": ...}}}``,
            with ``"inferred_from"`` added to inferred arguments. The value of a missing
            argument is ``None``.
        """
        arguments = {}
        for name, value in self.items():
            source = self.sources[name]
            arguments[name] = {"value": None if source == "missing" else value, "source": source}
            if name in self.inferred_from:
                arguments[name]["inferred_from"] = self.inferred_from[name]
        return {"status": self.status, "error": self.error, "arguments": arguments}


# The lines of a call drawn as a tree, as (text, note) pairs: "name = value" with the "="
# signs lined up, and a note on each value inferred from a function receiving **kwargs.
def tree(call):
    width = max(map(len, call), default=0)
    value_width = min(max((len(v) for k, v in call.items() if k in call.inferred_from), default=0), 40)
    rows = []
    for i, (name, value) in enumerate(call.items()):
        branch = "└─" if i == len(call) - 1 else "├─"
        if name in call.inferred_from:
            rows.append((f"{branch} {name:<{width}} = {value:<{value_width}}", f"# inferred from {call.inferred_from[name]}"))
        else:
            rows.append((f"{branch} {name:<{width}} = {value}", ""))
    return rows


# What the header says about a call that hasn't simply succeeded.
def status_text(call):
    return {"running": "running", "failed": f"failed: {call.error}"}.get(call.status, "")


class Parameters(dict):
    """The last call of each tracked method or function, as ``{name: Call}``.

    Printing it, or showing it in Jupyter, draws each call as a tree. Values inferred from
    a function receiving ``**kwargs`` are marked, and so are calls that failed or are
    still running.
    """

    def __init__(self):
        super().__init__()
        self._uncalled = {}  # functions not called yet, as name -> function giving their Call

    def _record(self, name, call):
        self._uncalled.pop(name, None)
        self[name] = call

    # Recompute the entries of functions not called yet: what their **kwargs are passed on to
    # may have been defined after them.
    def _refresh(self):
        for name, uncalled in self._uncalled.items():
            self[name] = uncalled()

    def to_dict(self):
        """All calls as plain data that can be saved as JSON.

        Returns
        -------
        dict
            ``{name: Call.to_dict()}`` for each tracked method or function.
        """
        self._refresh()
        return {name: call.to_dict() for name, call in self.items()}

    def to_json(self, path=None, indent=2):
        """All calls as JSON, see :meth:`to_dict`.

        Parameters
        ----------
        path : str or pathlib.Path, optional
            File to write the JSON to.
        indent : int, optional
            Indentation of the JSON.

        Returns
        -------
        str or None
            The JSON, or ``None`` when it is written to ``path``.
        """
        text = json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
        if path is None:
            return text
        Path(path).write_text(text + "\n", encoding="utf-8")

    # Text version, used by print() and the terminal.
    def __repr__(self):
        self._refresh()
        blocks = []
        for name, call in self.items():
            header = f"\033[1m{name}\033[0m"  # \033[1m = bold
            status = status_text(call)
            if status:
                color = 31 if call.status == "failed" else 2  # red, dim
                header += f"  \033[{color}m({status})\033[0m"
            rows = [f"{text}  \033[2m{note}\033[0m" if note else text for text, note in tree(call)]
            blocks.append("\n".join([header, *rows]))
        return "\n\n".join(blocks)

    # Clickable version, used by Jupyter; click a name to unfold its arguments.
    def _repr_html_(self):
        self._refresh()
        html = ""
        for name, call in self.items():
            status = status_text(call)
            if status:
                color = "#c00" if call.status == "failed" else "gray"
                status = f" <span style='color: {color}'>({escape(status)})</span>"
            rows = "\n".join(
                escape(text) + (f"  <span style='opacity: 0.6'>{escape(note)}</span>" if note else "")
                for text, note in tree(call)
            )
            html += f"<details><summary><b>{escape(name)}</b>{status}</summary><pre style='margin: 0 0 0 1.2em'>{rows}</pre></details>"
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
    except Exception:  # no source, e.g. typed into a plain python shell
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


# The parameters that func's **kwargs end up in, as {name: (value, source, receiving function)}:
# the passed value where given, else the default of the receiving function, else UNSET.
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
        receiver = getattr(callee, "__name__", type(callee).__name__)
        rest = dict(kwargs)
        for i, p in enumerate(parameters):
            if p.kind in (p.VAR_POSITIONAL, VAR_KEYWORD) or p.name in explicit:
                continue
            if i < n_positional and p.kind is not p.KEYWORD_ONLY:  # filled by a positional argument
                continue
            if p.name in rest:
                result.setdefault(p.name, (rest.pop(p.name), "passed", None))
            elif p.default is p.empty:
                result.setdefault(p.name, (UNSET, "missing", receiver))
            else:
                result.setdefault(p.name, (p.default, "inferred", receiver))
        inner = inspect.unwrap(getattr(callee, "__func__", callee))
        if parameters and parameters[-1].kind is VAR_KEYWORD and inspect.isfunction(inner) and inner not in seen:
            inner_local = {next(iter(inspect.signature(inner).parameters)): callee.__self__} if inspect.ismethod(callee) else {}
            for name, entry in forwarded(inner, inner_local, rest, seen).items():
                result.setdefault(name, entry)
    for name, value in kwargs.items():
        result.setdefault(name, (value, "passed", None))
    return result


# The arguments of a call as {name: (value, source, receiving function)}, without self.
# passed holds the names given in the call itself.
def describe(function, signature, arguments, passed):
    entries = {}
    for name, value in arguments.items():
        # Instead of one dict, list what **kwargs is passed on to, defaults included.
        if signature.parameters[name].kind is VAR_KEYWORD:
            for key, entry in forwarded(inspect.unwrap(function), arguments, value).items():
                entries.setdefault(key, entry)
        elif name != "self":
            source = "passed" if name in passed else "missing" if value is UNSET else "default"
            entries[name] = (value, source, None)
    return entries


# parameters_of(args) gives the Parameters to record a call in, or None to leave it out.
def track(function, parameters_of):
    signature = inspect.signature(function)

    # Records the call as running and returns where, or None when it isn't recorded.
    def start(args, kwargs):
        try:
            bound = signature.bind(*args, **kwargs)
        except TypeError:  # wrong arguments: the function raises its own error
            return None
        parameters = parameters_of(args)
        if parameters is None:
            return None
        passed = set(bound.arguments)
        bound.apply_defaults()
        call = Call(describe(function, signature, bound.arguments, passed), "running")
        parameters._record(function.__name__, call)
        return parameters, call

    @wraps(function)
    def wrapper(*args, **kwargs):
        started = start(args, kwargs)
        if started is None:
            return function(*args, **kwargs)
        parameters, call = started
        try:
            result = function(*args, **kwargs)
        except BaseException as error:
            call.status, call.error = "failed", error_text(error)
            raise
        else:
            call.status = "ok"
        finally:
            # Again at the end, so that this call is kept over nested calls of the same name.
            parameters._record(function.__name__, call)
        return result
    return wrapper


# track_class keeps the Parameters of each instance in its __dict__ under this name.
KEY = "_paramtrack_parameters"


def instance_parameters(instance):
    try:
        store = vars(instance)
    except TypeError:  # no __dict__
        return None
    if KEY not in store:
        store[KEY] = Parameters()
    return store[KEY]


# The Parameters of the instance a method is called on.
def method_parameters(args):
    return instance_parameters(args[0]) if args else None


# cls.parameters, giving each instance its own Parameters.
class PerInstance:
    def __get__(self, instance, owner=None):
        return self if instance is None else instance_parameters(instance)

    def __repr__(self):
        return "<parameters, kept per instance>"


def track_class(cls):
    """Track the arguments of every method of a class.

    Each call stores the method's arguments, defaults included, in the ``parameters`` of
    the instance it is called on, under the method's name, replacing those of the
    previous call. Keywords that a method passes on with ``**kwargs`` are listed together
    with the parameters and defaults of the function receiving them; those defaults are
    marked as inferred. Each call also records whether it succeeded.

    Parameters
    ----------
    cls : type
        The class to track. Its instances need a ``__dict__``.

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
    >>> telescope.parameters["observe"].status
    'ok'
    """
    if not any("__dict__" in vars(base) for base in cls.__mro__):
        raise TypeError(f"track_class keeps the parameters in each instance's __dict__, which {cls.__name__} doesn't have; add '__dict__' to __slots__")
    cls.parameters = PerInstance()
    for name, method in list(vars(cls).items()):
        if inspect.isfunction(method):
            setattr(cls, name, track(method, method_parameters))
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
    wrapper = track(function, lambda args: parameters)
    wrapper.parameters = parameters
    # Before the first call: the defaults, and UNSET for arguments without one.
    signature = inspect.signature(function)
    bound = signature.bind_partial()
    bound.apply_defaults()
    arguments = {name: bound.arguments.get(name, UNSET) for name in signature.parameters}
    parameters._uncalled[function.__name__] = lambda: Call(describe(function, signature, arguments, set()), "not called")
    parameters._refresh()
    return wrapper
