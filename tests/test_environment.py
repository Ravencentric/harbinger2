import os

import pytest

from harbinger.command import Environment


def test_environment_snapshots_inputs_and_keeps_merged_variants_independent() -> None:
    values = {"CI": "base"}
    base = Environment.new(values)
    values["CI"] = "changed"

    overrides = {"CI": "derived", "TOKEN": None}
    derived = base.merge(overrides)
    overrides["CI"] = "changed again"
    overrides["TOKEN"] = "restored"

    parent = {"TOKEN": "secret", "INHERITED": "parent"}
    assert base.overlay(parent) == {
        "CI": "base",
        "TOKEN": "secret",
        "INHERITED": "parent",
    }
    assert derived.overlay(parent) == {"CI": "derived", "INHERITED": "parent"}
    assert parent == {"TOKEN": "secret", "INHERITED": "parent"}


def test_environment_removals_survive_merging_and_can_be_replaced() -> None:
    removed = Environment.new({"TOKEN": None}).merge({"CI": "1"})
    restored = removed.merge({"TOKEN": "restored"})
    parent = {"TOKEN": "parent"}

    assert removed.overlay(parent) == {"CI": "1"}
    assert removed.overlay({}) == {"CI": "1"}
    assert restored.overlay(parent) == {"CI": "1", "TOKEN": "restored"}
    assert removed.overlay(parent) == {"CI": "1"}


def test_environment_overlay_uses_platform_case_rules_for_parent() -> None:
    environment = Environment.new({"Mixed": "override", "Remove": None})
    parent = {"mixed": "parent", "remove": "secret"}

    if os.name == "nt":
        expected = {"MIXED": "override"}
    else:
        expected = {"Mixed": "override", "mixed": "parent", "remove": "secret"}

    assert environment.overlay(parent) == expected
    assert parent == {"mixed": "parent", "remove": "secret"}


@pytest.mark.skipif(os.name != "nt", reason="Windows environment case rules")
@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"path": "first", "PATH": "last"}, {"PATH": "last"}),
        ({"path": "first", "PATH": None}, {}),
        ({"PATH": "first", "path": "last"}, {"PATH": "last"}),
        ({"PATH": None, "path": "last"}, {"PATH": "last"}),
    ],
)
def test_environment_merge_normalizes_incoming_keys_before_combining(
    overrides: dict[str, str | None], expected: dict[str, str]
) -> None:
    base = Environment.new({"PATH": "base"})
    derived = base.merge(overrides)

    assert derived.overlay({"Path": "parent"}) == expected
    assert base.overlay({}) == {"PATH": "base"}
