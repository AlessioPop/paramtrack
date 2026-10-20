# paramtrack

Remembers the arguments of each method's last call, defaults included.

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

In Jupyter, put `telescope.parameters` on the last line of a cell for a foldable view.

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
└─ filter   = 'V'
```

This works through chains of `**kwargs` and for calls like `self.method(**kwargs)` or `module.function(**kwargs)`. The source code has to be available: in a plain `python` shell, only the passed keywords are shown.

### Functions

`track_function` does the same for plain functions and stores the arguments as `function.parameters`:

```python
from paramtrack import track_function

@track_function
def observe(target, exposure=30, filter="V"):
    ...

observe("Vega")

print(observe.parameters)
```
