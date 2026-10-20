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
