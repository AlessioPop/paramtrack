import inspect
from functools import wraps
from html import escape

__all__ = ["track_class"]


# "name = value" lines with the "=" signs lined up, drawn as a tree.
def tree(arguments):
    width = max(map(len, arguments), default=0)
    lines = [f"{k:<{width}} = {v}" for k, v in arguments.items()]
    return [f"├─ {line}" for line in lines[:-1]] + [f"└─ {line}" for line in lines[-1:]]


class Parameters(dict):
    # Text version, used by print() and the terminal.
    def __repr__(self):
        blocks = []
        for name, arguments in self.items():
            blocks.append("\n".join([f"\033[1m{name}\033[0m", *tree(arguments)]))  # \033[1m = bold
        return "\n\n".join(blocks)

    # Clickable version, used by Jupyter; click a method name to unfold it.
    def _repr_html_(self):
        html = ""
        for name, arguments in self.items():
            lines = escape("\n".join(tree(arguments)))
            html += f"<details><summary><b>{name}</b></summary><pre style='margin: 0 0 0 1.2em'>{lines}</pre></details>"
        return html


def track(method, parameters):
    @wraps(method)
    def wrapper(*args, **kwargs):
        bound = inspect.signature(method).bind(*args, **kwargs)
        bound.apply_defaults()
        arguments = {}
        for name, value in bound.arguments.items():
            # Unpack **kwargs so each keyword gets its own line instead of one dict.
            if bound.signature.parameters[name].kind is inspect.Parameter.VAR_KEYWORD:
                arguments.update(value)
            elif name != "self":
                arguments[name] = value
        parameters[method.__name__] = {k: repr(v) for k, v in arguments.items()}
        return method(*args, **kwargs)
    return wrapper


# Class decorator: track every method and store the arguments as cls.parameters.
def track_class(cls):
    cls.parameters = Parameters()
    for name, method in list(vars(cls).items()):
        if inspect.isfunction(method):
            setattr(cls, name, track(method, cls.parameters))
    return cls
