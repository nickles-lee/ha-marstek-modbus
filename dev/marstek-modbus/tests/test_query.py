"""Check the read-only query command defaults."""

from script.query import build_parser


def test_default_spacing() -> None:
    """Use 160 ms for a new query and accept an explicit choice."""
    assert build_parser().parse_args(["192.0.2.10", "--model", "e_v2"]).spacing == 0.16
    assert (
        build_parser()
        .parse_args(["192.0.2.10", "--model", "e_v2", "--spacing", "0.08"])
        .spacing
        == 0.08
    )
