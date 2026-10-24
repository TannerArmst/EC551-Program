import json
import unittest
from pathlib import Path

import logic_synthesis1 as ls


class LogicSynthesisTests(unittest.TestCase):
    def test_sop_input(self):
        actual = ls.sop_on_set(["a", "b", "c"], "ab+c'")
        self.assertEqual(actual, {0, 2, 4, 6, 7})

    def test_graph_example_matches_sop(self):
        path = Path(__file__).parent / "examples" / "example_circuit.json"
        with path.open(encoding="utf-8") as file:
            circuit = json.load(file)

        variables, on_set = ls.circuit_on_set(circuit)

        self.assertEqual(variables, ["a", "b", "c"])
        self.assertEqual(on_set, ls.sop_on_set(variables, "ab+c'"))

    def test_evaluate_input_assignment(self):
        engine = ls.LogicEngine(
            ["a", "b", "c"],
            ls.sop_on_set(["a", "b", "c"], "ab+c'")
        )

        self.assertEqual(engine.evaluate_bits("1,1,1"), 1)
        self.assertEqual(engine.evaluate_bits("0,0,1"), 0)

    def test_unknown_graph_signal_is_rejected(self):
        circuit = {
            "inputs": ["a"],
            "gates": [
                {"type": "NOT", "inputs": ["missing"], "output": "F"}
            ],
            "output": "F"
        }

        with self.assertRaises(ValueError):
            ls.circuit_on_set(circuit)


if __name__ == "__main__":
    unittest.main()
