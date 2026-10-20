# paramtrack

[![PyPI](https://img.shields.io/pypi/v/paramtrack)](https://pypi.org/project/paramtrack/)
[![Tests](https://github.com/AlessioPop/paramtrack/actions/workflows/tests.yml/badge.svg)](https://github.com/AlessioPop/paramtrack/actions/workflows/tests.yml)
[![Documentation](https://readthedocs.org/projects/paramtrack/badge/?version=latest)](https://paramtrack.readthedocs.io/en/latest/)

Remembers the arguments of each method's last call, defaults included, and whether the call succeeded.

## Install

```bash
pip install paramtrack
```

## Usage

```python
from paramtrack import track_class

@track_class
class Telescope:
    def observe(self, target, exposure=30, filter="V"):
        ...

telescope = Telescope()
telescope.observe("Vega", exposure=60)

print(telescope.parameters)
```

```
observe
├─ target   = 'Vega'
├─ exposure = 60
└─ filter   = 'V'
```

Each instance keeps its own `parameters`. In Jupyter, put `telescope.parameters` on the last line of a cell for a foldable view.

### Forwarded `**kwargs`

When a method passes its `**kwargs` on to another function, the parameters of that function are listed too, defaults included:

```python
def observe(target, exposure=30, filter="V"):
    ...

@track_class
class Telescope:
    def run(self, **kwargs):
        return observe("Vega", **kwargs)

telescope = Telescope()
telescope.run(exposure=60)

print(telescope.parameters)
```

```
run
├─ exposure = 60
└─ filter   = 'V'  # inferred from observe
```

Values that weren't passed but read from the receiving function are marked `# inferred from ...`: they are what that function uses by default, unless the method changes the keywords before passing them on. This works through chains of `**kwargs` and for calls like `self.method(**kwargs)` or `module.function(**kwargs)`. The source code has to be available: in a plain `python` shell, only the passed keywords are shown.

### Functions

`track_function` does the same for plain functions and stores the arguments as `function.parameters`. Before the first call, it shows the defaults, with `?` for arguments that have none:

```python
from paramtrack import track_function

@track_function
def observe(target, exposure=30, filter="V"):
    ...

print(observe.parameters)
```

```
observe
├─ target   = ?
├─ exposure = 30
└─ filter   = 'V'
```

After a call such as `observe("Vega")`, the values of that call are shown instead.

### Failed calls

Each call records whether it succeeded. A failed call is marked in the tree and keeps its arguments, so you can see what it ran with:

```
observe  (failed: ValueError: no such target)
├─ target   = 'Vgea'
├─ exposure = 30
└─ filter   = 'V'
```

Each entry also has `.status` (`"ok"`, `"failed"`, `"running"` or `"not called"`) and `.error`:

```python
telescope.parameters["observe"].status  # 'failed'
telescope.parameters["observe"].error   # 'ValueError: no such target'
```

### Export

Save the parameters as JSON, with the status of each call and where each value came from (`passed`, `default`, `inferred` or `missing`):

```python
telescope.parameters.to_json("parameters.json")
data = telescope.parameters.to_dict()
```

```json
"run": {
  "status": "ok",
  "error": null,
  "arguments": {
    "exposure": {"value": "60", "source": "passed"},
    "filter": {"value": "'V'", "source": "inferred", "inferred_from": "observe"}
  }
}
```

## Development

Run the tests:

```bash
uv run pytest
```

Build the docs into `docs/_build/html`:

```bash
uv run --with-requirements docs/requirements.txt sphinx-build docs docs/_build/html
```
