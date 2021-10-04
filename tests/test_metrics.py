import unittest

import dump1090exporter.metrics


class TestMetrics(unittest.TestCase):
    """Check metrics spec structure"""

    def test_specification(self):
        """check structure of specification"""
        self.assertIsInstance(dump1090exporter.metrics.Specs, dict)

        self.assertIn("aircraft", dump1090exporter.metrics.Specs)
        v = dump1090exporter.metrics.Specs["aircraft"]
        self.assertIsInstance(v, tuple)
        for i in v:
            self.assertIsInstance(i, tuple)
            self.assertEqual(len(i), 3)

        self.assertIn("stats", dump1090exporter.metrics.Specs)
        v = dump1090exporter.metrics.Specs["stats"]
        self.assertIsInstance(v, dict)
        for k1, v1 in v.items():
            self.assertIsInstance(k1, str)
            for i in v1:
                self.assertIsInstance(i, tuple)
                self.assertEqual(len(i), 3)
