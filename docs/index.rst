paramtrack
==========

Welcome to the documentation for ``paramtrack``, a small Python package that remembers
the arguments of each method's last call, defaults included.

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

**0.2.0 (2026-10-20)**

- Keywords passed on with ``**kwargs`` are listed with the parameters and defaults of the function receiving them
- New ``track_function`` decorator for plain functions

**0.1.1 (2026-10-20)**

- ``**kwargs`` are listed one keyword per line instead of as one dict

**0.1.0 (2026-10-20)**

- Initial release with ``track_class``
