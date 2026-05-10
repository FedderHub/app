"""Pure-function unit tests for helpers in ``app.routers.jobs``.

These run without a database or HTTP layer.  They directly exercise the
mathematical helpers used by the FedAvg pipeline and the JSON parsers used
when reading stored snapshots back.
"""
from __future__ import annotations

import pytest

from app.routers.jobs import (
    parse_snapshot,
    parse_weights,
    weighted_average,
)


class TestWeightedAverage:
    def test_simple_weighted_mean(self):
        # (1.0 * 100 + 2.0 * 300) / 400 = 1.75
        assert weighted_average([1.0, 2.0], [100, 300]) == pytest.approx(1.75)

    def test_uniform_weights_equals_simple_mean(self):
        assert weighted_average([1.0, 3.0], [10, 10]) == pytest.approx(2.0)

    def test_drops_none_values(self):
        # (2.0 * 200) / 200 = 2.0
        assert weighted_average([None, 2.0], [100, 200]) == pytest.approx(2.0)

    def test_all_none_returns_none(self):
        assert weighted_average([None, None], [10, 20]) is None

    def test_zero_total_returns_none(self):
        assert weighted_average([1.0, 2.0], [0, 0]) is None

    def test_empty_inputs_return_none(self):
        assert weighted_average([], []) is None

    def test_single_value(self):
        assert weighted_average([5.0], [42]) == pytest.approx(5.0)


class TestParseWeights:
    def test_parses_valid_json_list(self):
        assert parse_weights("[1.0, 2.0, 3.0]") == [1.0, 2.0, 3.0]

    def test_returns_empty_for_none(self):
        assert parse_weights(None) == []

    def test_returns_empty_for_empty_string(self):
        assert parse_weights("") == []

    def test_returns_empty_for_invalid_json(self):
        assert parse_weights("not json at all") == []

    def test_returns_empty_for_non_list_json(self):
        assert parse_weights('{"x": 1}') == []
        assert parse_weights("42") == []
        assert parse_weights('"a string"') == []

    def test_coerces_ints_to_floats(self):
        assert parse_weights("[1, 2, 3]") == [1.0, 2.0, 3.0]
        assert all(isinstance(v, float) for v in parse_weights("[1, 2, 3]"))


class TestParseSnapshot:
    def test_parses_valid_dict(self):
        assert parse_snapshot('{"a": 1, "b": "x"}') == {"a": 1, "b": "x"}

    def test_parses_nested_dict(self):
        result = parse_snapshot('{"global_weights": [1.0, 2.0]}')
        assert result == {"global_weights": [1.0, 2.0]}

    def test_returns_empty_for_none(self):
        assert parse_snapshot(None) == {}

    def test_returns_empty_for_invalid_json(self):
        assert parse_snapshot("not json") == {}

    def test_returns_empty_for_non_dict_json(self):
        assert parse_snapshot("[1, 2, 3]") == {}
        assert parse_snapshot("42") == {}
        assert parse_snapshot('"string"') == {}
