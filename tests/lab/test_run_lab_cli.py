import pytest

from scripts.lab.run_lab import build_parser, selected_parts


def test_all_selects_every_part_in_order():
    assert selected_parts(build_parser().parse_args(["--all"])) == [1, 2, 3, 4, 5, 6, 7]


def test_part_can_be_repeated():
    assert selected_parts(
        build_parser().parse_args(["--part", "4", "--part", "1"])
    ) == [4, 1]


def test_an_action_is_required():
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args([])
    assert exc.value.code == 2


def test_rejects_unknown_parts():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--part", "9"])
