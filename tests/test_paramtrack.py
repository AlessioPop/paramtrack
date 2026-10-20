import json

import pytest

from paramtrack import track_class, track_function


def observe(target, exposure=30, filter="V"):
    return target


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

        def fail(self, reason="bad prior"):
            raise ValueError(reason)

        def status_inside(self, x=1):
            return self.parameters["status_inside"].status

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

    assert expose("Vega") == "Vega"
    assert expose.parameters == {"expose": {"target": "'Vega'", "exposure": "30"}}


def test_track_function_shows_defaults_before_first_call():
    @track_function
    def expose(target, *frames, exposure=30, **options):
        return target

    assert expose.parameters == {"expose": {"target": "?", "frames": "()", "exposure": "30"}}
    assert "├─ target   = ?" in repr(expose.parameters)

    expose("Vega")
    assert expose.parameters["expose"]["target"] == "'Vega'"


def test_kwargs_before_first_call():
    @track_function
    def run(**kwargs):
        return observe(**kwargs)

    assert run.parameters["run"] == {"target": "?", "exposure": "30", "filter": "'V'"}


def test_kwargs_before_first_call_to_function_defined_later():
    @track_function
    def run(**kwargs):
        return later(**kwargs)

    def later(speed=1):
        return speed

    assert "└─ speed = 1" in repr(run.parameters)
    assert run.parameters["run"] == {"speed": "1"}


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
    # The call made from outside is kept, not the innermost one.
    assert countdown.parameters["countdown"] == {"n": "3", "step": "1"}


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


def test_each_instance_has_its_own_parameters(telescope):
    other = type(telescope)("Webb")
    telescope.observe("Vega")
    other.observe("Sirius", exposure=10)

    assert telescope.parameters["observe"]["target"] == "'Vega'"
    assert other.parameters["observe"] == {"target": "'Sirius'", "exposure": "10", "filter": "'V'"}
    assert other.parameters["__init__"] == {"name": "'Webb'"}


def test_sources_of_values(telescope):
    telescope.observe("Vega", exposure=60)
    assert telescope.parameters["observe"].sources == {"target": "passed", "exposure": "passed", "filter": "default"}

    telescope.run(exposure=60)
    call = telescope.parameters["run"]
    assert call.sources == {"exposure": "passed", "filter": "inferred"}
    assert call.inferred_from == {"filter": "observe"}


def test_inferred_values_are_marked(telescope):
    telescope.run(exposure=60)
    lines = repr(telescope.parameters).splitlines()
    assert "├─ exposure = 60" in lines
    assert any(line.startswith("└─ filter   = 'V'") and "# inferred from observe" in line for line in lines)
    assert "# inferred from observe" in telescope.parameters._repr_html_()


def test_missing_values_through_kwargs():
    @track_function
    def run(**kwargs):
        return observe(**kwargs)

    call = run.parameters["run"]
    assert call.status == "not called"
    assert call.sources["target"] == "missing"
    assert call.inferred_from["target"] == "observe"


def test_failed_call_is_recorded(telescope):
    with pytest.raises(ValueError, match="bad prior"):
        telescope.fail()

    call = telescope.parameters["fail"]
    assert call == {"reason": "'bad prior'"}
    assert call.status == "failed"
    assert call.error == "ValueError: bad prior"
    assert "(failed: ValueError: bad prior)" in repr(telescope.parameters)


def test_status_while_running_and_after(telescope):
    assert telescope.status_inside() == "running"
    assert telescope.parameters["status_inside"].status == "ok"
    assert telescope.parameters["status_inside"].error is None


def test_wrong_arguments_raise_the_functions_own_error(telescope):
    with pytest.raises(TypeError, match="observe"):
        telescope.observe()
    assert "observe" not in telescope.parameters


def test_unrepresentable_values_dont_break_the_call(telescope):
    class Broken:
        def __repr__(self):
            raise RuntimeError

    assert isinstance(telescope.observe(Broken()), Broken)
    assert telescope.parameters["observe"]["target"] == "<Broken object>"


def test_export(telescope, tmp_path):
    telescope.run(exposure=60)
    with pytest.raises(ValueError):
        telescope.fail("no data")

    data = telescope.parameters.to_dict()
    assert data["run"] == {
        "status": "ok",
        "error": None,
        "arguments": {
            "exposure": {"value": "60", "source": "passed"},
            "filter": {"value": "'V'", "source": "inferred", "inferred_from": "observe"},
        },
    }
    assert data["fail"]["status"] == "failed"
    assert data["fail"]["error"] == "ValueError: no data"

    path = tmp_path / "parameters.json"
    assert telescope.parameters.to_json(path) is None
    assert json.loads(path.read_text()) == data
    assert json.loads(telescope.parameters.to_json()) == data


def test_export_before_first_call():
    @track_function
    def expose(target, exposure=30):
        return target

    assert expose.parameters.to_dict() == {
        "expose": {
            "status": "not called",
            "error": None,
            "arguments": {
                "target": {"value": None, "source": "missing"},
                "exposure": {"value": "30", "source": "default"},
            },
        }
    }


def test_slots_without_dict_are_rejected():
    class Slotted:
        __slots__ = ("x",)

    with pytest.raises(TypeError, match="__dict__"):
        track_class(Slotted)
