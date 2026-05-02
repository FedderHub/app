"""Supplemental tests for fedavg_mock.federated_average_state_dicts.

The existing test_phase3_integration.py covers the main happy paths and
``empty_input`` / ``mismatched_layers`` errors.  This file fills the
remaining error branches so coverage of the Phase 3 aggregation
function is complete.
"""
import unittest

from fedavg_mock import federated_average_state_dicts


class TestStateDictAggregationEdgeCases(unittest.TestCase):

    def test_mismatched_lengths_raises(self):
        """Different number of state dicts vs sample counts -> ValueError."""
        sd1 = {"layer": {"data": [1.0], "shape": [1]}}
        sd2 = {"layer": {"data": [2.0], "shape": [1]}}
        with self.assertRaises(ValueError) as ctx:
            federated_average_state_dicts([sd1, sd2], [100])
        self.assertIn("Mismatch", str(ctx.exception))

    def test_negative_sample_count_raises(self):
        """Negative sample counts are invalid -> ValueError."""
        sd1 = {"layer": {"data": [1.0], "shape": [1]}}
        sd2 = {"layer": {"data": [2.0], "shape": [1]}}
        with self.assertRaises(ValueError) as ctx:
            federated_average_state_dicts([sd1, sd2], [100, -50])
        self.assertIn("non-negative", str(ctx.exception))

    def test_zero_total_samples_raises(self):
        """All-zero sample counts -> ValueError (division-by-zero guard)."""
        sd1 = {"layer": {"data": [1.0], "shape": [1]}}
        with self.assertRaises(ValueError) as ctx:
            federated_average_state_dicts([sd1], [0])
        self.assertIn("greater than zero", str(ctx.exception))

    def test_layer_data_size_mismatch_raises(self):
        """Same layer name but different data lengths between clients -> ValueError."""
        sd1 = {"layer": {"data": [1.0, 2.0, 3.0], "shape": [3]}}
        sd2 = {"layer": {"data": [4.0, 5.0], "shape": [2]}}
        with self.assertRaises(ValueError) as ctx:
            federated_average_state_dicts([sd1, sd2], [100, 100])
        self.assertIn("size mismatch", str(ctx.exception))

    def test_three_clients_weighted_correctly(self):
        """Sanity check: 3-client weighted aggregation matches manual calculation."""
        sd_a = {"w": {"data": [1.0, 1.0], "shape": [2]}}
        sd_b = {"w": {"data": [2.0, 2.0], "shape": [2]}}
        sd_c = {"w": {"data": [3.0, 3.0], "shape": [2]}}

        # Sample sizes: 100, 200, 700 -> total 1000
        # Expected: (100*1 + 200*2 + 700*3) / 1000 = 2.6
        result = federated_average_state_dicts([sd_a, sd_b, sd_c], [100, 200, 700])
        self.assertAlmostEqual(result["w"]["data"][0], 2.6, places=6)
        self.assertAlmostEqual(result["w"]["data"][1], 2.6, places=6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
