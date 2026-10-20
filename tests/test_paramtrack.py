import json

import pytest

from paramtrack import track_class, track_function


def observe(target, exposure=30, filter="V"):
    return target


# A fresh class per test: parameters belongs to the class, so instances share it.
@pytest.fixture
def telescope():
    @track_class
    class Telescope:
        def __init__(self, name="Hubble"):
            self.name = name

        def observe(self, target, exposure=30, filter="V"):
            """Point at a target."""
            return target

        def _private(self, x=1):
            return x

        def run(self, **kwargs):
            return observe("Vega", **kwargs)

        def run_by_keyword(self, **kwargs):
            return observe(target="Vega", **kwargs)

        def run_method(self, **kwargs):
            return self.observe("Vega", **kwargs)

        def dump(self, obj, **kwargs):
            return json.dumps(obj, **kwargs)

        def store(self, **kwargs):
            self.kwargs = kwargs

    return Telescope()


def test_records_last_call_with_defaults(telescope):
    telescope.observe("Vega", exposure=60)
    assert telescope.parameters["observe"] == {"target": "'Vega'", "exposure": "60", "filter": "'V'"}

    telescope.observe("Sirius")
    assert telescope.parameters["observe"] == {"target": "'Sirius'", "exposure": "30", "filter": "'V'"}


def test_lists_only_called_methods(telescope):
    assert list(telescope.parameters) == ["__init__"]
    telescope._private()
    assert list(telescope.parameters) == ["__init__", "_private"]


def test_keeps_return_value_and_metadata(telescope):
    assert telescope.observe("Vega") == "Vega"
    assert type(telescope).observe.__name__ == "observe"
    assert type(telescope).observe.__doc__ == "Point at a target."


def test_kwargs_show_defaults_of_receiving_function(telescope):
    telescope.run(exposure=60)
    assert telescope.parameters["run"] == {"exposure": "60", "filter": "'V'"}


def test_kwargs_skip_keywords_given_explicitly(telescope):
    telescope.run_by_keyword(filter="R")
    assert telescope.parameters["run_by_keyword"] == {"exposure": "30", "filter": "'R'"}


def test_kwargs_passed_to_own_method(telescope):
    telescope.run_method(filter="R")
    assert telescope.parameters["run_method"] == {"exposure": "30", "filter": "'R'"}
    assert telescope.parameters["observe"] == {"target": "'Vega'", "exposure": "30", "filter": "'R'"}


def test_kwargs_passed_to_module_function(telescope):
    telescope.dump({"a": 1}, indent=2)
    arguments = telescope.parameters["dump"]
    assert arguments["obj"] == "{'a': 1}"
    assert arguments["indent"] == "2"
    assert arguments["sort_keys"] == "False"


def test_kwargs_not_passed_on_are_listed_as_given(telescope):
    telescope.store(x=1, y=2)
    assert telescope.parameters["store"] == {"x": "1", "y": "2"}


def test_track_function():
    @track_function
    def expose(target, exposure=30):
        return target

    assert expose.parameters == {}
    assert expose("Vega") == "Vega"
    assert expose.parameters == {"expose": {"target": "'Vega'", "exposure": "30"}}


def test_kwargs_followed_through_a_chain():
    def inner(x, y=2, *, z="z"):
        return x

    def middle(scale=1.0, **kwargs):
        return inner(0, **kwargs)

    @track_function
    def outer(**kwargs):
        return middle(**kwargs)

    outer(z="Z", scale=5)
    assert outer.parameters["outer"] == {"scale": "5", "y": "2", "z": "'Z'"}


def test_recursion_through_kwargs_terminates():
    @track_function
    def countdown(n=3, **kwargs):
        if n:
            return countdown(n - 1, **kwargs)

    countdown(step=1)
    assert countdown.parameters["countdown"] == {"n": "0", "step": "1"}


def test_without_source_lists_kwargs_as_given():
    namespace = {"observe": observe}
    exec("def run(**kwargs):\n    return observe('Vega', **kwargs)", namespace)
    run = track_function(namespace["run"])

    run(exposure=60)
    assert run.parameters["run"] == {"exposure": "60"}


def test_text_and_html_views(telescope):
    telescope.observe("Vega")
    text = repr(telescope.parameters)
    assert "├─ target   = 'Vega'" in text
    assert "└─ filter   = 'V'" in text

    html = telescope.parameters._repr_html_()
    assert "<details><summary><b>observe</b></summary>" in html
