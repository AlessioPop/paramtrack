Usage
=====

Classes
-------

Decorate a class with :func:`~paramtrack.track_class`. Every call to one of its methods
stores the arguments in ``parameters``, defaults included:

.. code-block:: python

   from paramtrack import track_class

   @track_class
   class Telescope:
       def observe(self, target, exposure=30, filter="V"):
           ...

   telescope = Telescope()
   telescope.observe("Vega", exposure=60)

   print(telescope.parameters)

.. code-block:: text

   observe
   ├─ target   = 'Vega'
   ├─ exposure = 60
   └─ filter   = 'V'

A method shows up once it has been called, and each call replaces the arguments of the
previous one. Each instance keeps its own ``parameters``.

In Jupyter, put ``telescope.parameters`` on the last line of a cell for a foldable view:
click a method name to unfold its arguments.

Forwarded ``**kwargs``
----------------------

When a method passes its ``**kwargs`` on to another function, the parameters of that
function are listed too, defaults included:

.. code-block:: python

   def observe(target, exposure=30, filter="V"):
       ...

   @track_class
   class Telescope:
       def run(self, **kwargs):
           return observe("Vega", **kwargs)

   telescope = Telescope()
   telescope.run(exposure=60)

   print(telescope.parameters)

.. code-block:: text

   run
   ├─ exposure = 60
   └─ filter   = 'V'  # inferred from observe

``target`` is left out because ``run`` fills it in itself. ``filter`` wasn't passed, so its
value is read from ``observe`` and marked ``# inferred from observe``: it is what
``observe`` uses by default, unless the method changes the keywords before passing them
on. In Jupyter the note is greyed out. This also works through chains
of ``**kwargs`` and for calls like ``self.method(**kwargs)`` or ``module.function(**kwargs)``.

Functions
---------

:func:`~paramtrack.track_function` does the same for plain functions and stores the
arguments as ``function.parameters``. Before the first call, it shows the defaults, with
``?`` for arguments that have none:

.. code-block:: python

   from paramtrack import track_function

   @track_function
   def observe(target, exposure=30, filter="V"):
       ...

   print(observe.parameters)

.. code-block:: text

   observe
   ├─ target   = ?
   ├─ exposure = 30
   └─ filter   = 'V'

Each call replaces this with the values of that call:

.. code-block:: python

   observe("Vega")

   print(observe.parameters)

.. code-block:: text

   observe
   ├─ target   = 'Vega'
   ├─ exposure = 30
   └─ filter   = 'V'

Failed calls
------------

Each call records whether it succeeded. A failed call is marked in the tree and keeps its
arguments, so you can see what it ran with:

.. code-block:: text

   observe  (failed: ValueError: no such target)
   ├─ target   = 'Vgea'
   ├─ exposure = 30
   └─ filter   = 'V'

Each entry of ``parameters`` is a :class:`~paramtrack.Call`: a dict of the arguments with
a ``status`` (``"ok"``, ``"failed"``, ``"running"`` or ``"not called"``) and an ``error``:

.. code-block:: python

   telescope.parameters["observe"].status  # 'failed'
   telescope.parameters["observe"].error   # 'ValueError: no such target'

While a call is still running, for example a long fit, it is marked ``(running)``.

Export
------

:meth:`~paramtrack.Parameters.to_dict` and :meth:`~paramtrack.Parameters.to_json` give the
parameters as plain data, with the status of each call and where each value came from:

- ``passed``: given in the call
- ``default``: the default of the function itself
- ``inferred``: read from the function receiving ``**kwargs``, named in ``inferred_from``
- ``missing``: no value yet, shown as ``?``

.. code-block:: python

   telescope.parameters.to_json("parameters.json")
   data = telescope.parameters.to_dict()

.. code-block:: json

   {
     "run": {
       "status": "ok",
       "error": null,
       "arguments": {
         "exposure": {"value": "60", "source": "passed"},
         "filter": {"value": "'V'", "source": "inferred", "inferred_from": "observe"}
       }
     }
   }

Good to know
------------

- Values are recorded when the call starts. If a call to a method of the same name happens
  inside it, e.g. through ``super()`` or recursion, the outer call is the one kept.
- ``track_class`` keeps the parameters in each instance's ``__dict__``, so a class with
  ``__slots__`` needs ``"__dict__"`` among them.
- For generators and ``async`` functions, the status says whether creating the generator
  or coroutine succeeded, not whether it ran to the end.
- Values are stored as their ``repr``, e.g. ``"'Vega'"`` for the string ``Vega``.
- ``?`` marks an argument without a value: a function argument without a default before
  the first call, or a required parameter of the function receiving ``**kwargs`` that
  wasn't passed.
- To find where ``**kwargs`` go, ``paramtrack`` reads the source code of the method
  without running it. If the method changes the keywords before passing them on, the
  defaults shown are still those of the receiving function. Without source code, as in a
  plain ``python`` shell, only the passed keywords are shown.
