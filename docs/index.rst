paramtrack
==========

Welcome to the documentation for ``paramtrack``, a small Python package that remembers
the arguments of each method's last call, defaults included, and whether the call
succeeded.

Many parameters never show up in the call itself: defaults, and keywords passed on with
``**kwargs`` to functions further down. ``paramtrack`` lists them all, so you can see
what a method actually ran with.

If you find a bug or want to request a feature, please create an
`issue on GitHub <https://github.com/AlessioPop/paramtrack/issues>`_.

User Guide:
+++++++++++

.. toctree::
   :maxdepth: 2

   installation
   usage
   api

Changelog:
++++++++++

**Unreleased**

- Each instance of a tracked class keeps its own ``parameters``; before, all instances of a class shared them
- Values read from the function receiving ``**kwargs`` are marked ``# inferred from ...``
- Each call records its status (``ok``, ``failed``, ``running``) and the error of a failed call
- New ``to_dict`` and ``to_json`` to export the parameters, with the status and the source of each value
- When calls of the same name are nested, e.g. through ``super()`` or recursion, the outer call is kept
- A value whose ``repr`` fails, or a call with wrong arguments, no longer breaks tracking

**0.3.0 (2026-10-20)**

- ``track_function`` shows the defaults before the first call, with ``?`` for arguments that have none
- Required parameters of the function receiving ``**kwargs`` are shown as ``?`` when not passed

**0.2.0 (2026-10-20)**

- Keywords passed on with ``**kwargs`` are listed with the parameters and defaults of the function receiving them
- New ``track_function`` decorator for plain functions

**0.1.1 (2026-10-20)**

- ``**kwargs`` are listed one keyword per line instead of as one dict

**0.1.0 (2026-10-20)**

- Initial release with ``track_class``
