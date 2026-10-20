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
previous one.

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
   └─ filter   = 'V'

``target`` is left out because ``run`` fills it in itself. This also works through chains
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

Good to know
------------

- ``parameters`` belongs to the class, so all instances of a class share it.
- Values are stored as their ``repr``, e.g. ``"'Vega'"`` for the string ``Vega``.
- ``?`` marks an argument without a value: a function argument without a default before
  the first call, or a required parameter of the function receiving ``**kwargs`` that
  wasn't passed.
- To find where ``**kwargs`` go, ``paramtrack`` reads the source code of the method
  without running it. If the method changes the keywords before passing them on, the
  defaults shown are still those of the receiving function. Without source code, as in a
  plain ``python`` shell, only the passed keywords are shown.
