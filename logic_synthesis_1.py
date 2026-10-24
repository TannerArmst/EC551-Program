"""EC551 Programming Assignment 1: single-output logic synthesis engine.

AI acknowledgment: This revision was developed with assistance from OpenAI
ChatGPT for implementation, debugging, documentation, and test development.
Review and understand the code before presenting it; adjust this acknowledgment
to accurately describe any additional assistance used by your team.

Python 3.9+; standard library only. Run: python logic_synthesis.py
"""

import csv
import json
import re
from itertools import combinations
from pathlib import Path



MAX_INPUTS = 8
MAX_COVER_STATES = 200_000
GATE_TYPES = {"AND", "OR", "NOT", "BUF", "NAND", "NOR", "XOR", "XNOR"}


def validate_variables(variables, single_letter=False):
    """Check names and preserve their order (first input is the MSB)."""
    if not isinstance(variables, list) or not 1 <= len(variables) <= MAX_INPUTS:
        raise ValueError(f"Provide between 1 and {MAX_INPUTS} input variables.")
    pattern = r"[A-Za-z]" if single_letter else r"[A-Za-z_][A-Za-z0-9_]*"
    if any(not isinstance(v, str) or not re.fullmatch(pattern, v) for v in variables):
        raise ValueError("SOP inputs must be single ASCII letters." if single_letter
                         else "Circuit input names must be ASCII identifiers.")
    if len(set(variables)) != len(variables):
        raise ValueError("Input variable names must be unique.")
    return list(variables)


def input_values(index, variables):
    """Convert a truth-table row number to a dictionary of input bits."""
    bits = format(index, f"0{len(variables)}b")
    return {name: int(bit) for name, bit in zip(variables, bits)}


def sop_on_set(variables, expression):
    """Parse SOP and evaluate all rows. A contradictory product equals zero."""
    validate_variables(variables, single_letter=True)
    expression = re.sub(r"\s+", "", expression)
    if not expression:
        raise ValueError("Enter an SOP expression.")
    parsed_terms = []
    for product in expression.split("+"):
        if not product:
            raise ValueError("A product term is missing beside a + sign.")
        if product == "0":
            continue
        if product == "1":
            parsed_terms.append({})
            continue
        literals = {}
        contradiction = False
        position = 0
        while position < len(product):
            match = re.match(r"([A-Za-z])('?)", product[position:])
            if not match:
                raise ValueError("Use letters, apostrophes for NOT, and + for OR.")
            name, complement = match.groups()
            if name not in variables:
                raise ValueError(f"Undeclared input variable: {name}")
            required_bit = 0 if complement else 1
            if name in literals and literals[name] != required_bit:
                contradiction = True
            literals[name] = required_bit
            position += match.end()
        if not contradiction:
            parsed_terms.append(literals)
    on_set = set()
    for index in range(2 ** len(variables)):
        values = input_values(index, variables)
        if any(all(values[name] == bit for name, bit in term.items())
               for term in parsed_terms):
            on_set.add(index)
    return on_set


def validate_circuit(data):
    """Validate a single-output DAG and put its gates in dependency order.

    Gates may appear in any order in the JSON file. A signal has exactly one
    driver. String signals "0" and "1" are reserved constant connections.
    """
    if not isinstance(data, dict):
        raise ValueError("The JSON circuit must be an object.")
    variables = validate_variables(data.get("inputs"))
    gates = data.get("gates")
    output = data.get("output")
    if not isinstance(gates, list):
        raise ValueError("The circuit must contain a gates list.")
    if not isinstance(output, str):
        raise ValueError("The circuit must name one output signal.")

    known = set(variables) | {"0", "1"}
    normalized = []
    for index, gate in enumerate(gates):
        if not isinstance(gate, dict):
            raise ValueError(f"Gate {index} must be an object.")
        kind = gate.get("type")
        inputs = gate.get("inputs")
        result = gate.get("output")
        if not isinstance(kind, str) or kind.upper() not in GATE_TYPES:
            raise ValueError(f"Gate {index}: unsupported type {kind!r}.")
        kind = kind.upper()
        if not isinstance(inputs, list) or any(not isinstance(x, str) for x in inputs):
            raise ValueError(f"Gate {index}: inputs must be a list of signal names.")
        if kind in {"NOT", "BUF"}:
            if len(inputs) != 1:
                raise ValueError(f"{kind} requires exactly one input.")
        elif len(inputs) < 2:
            raise ValueError(f"{kind} requires at least two inputs.")
        if not isinstance(result, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", result):
            raise ValueError(f"Gate {index}: output must be an ASCII identifier.")
        if result in known:
            raise ValueError(f"Signal {result!r} has multiple drivers or reuses an input.")
        known.add(result)
        normalized.append({"type": kind, "inputs": list(inputs), "output": result})

    for gate in normalized:
        for signal in gate["inputs"]:
            if signal not in known:
                raise ValueError(f"Unknown signal {signal!r} feeding {gate['output']!r}.")
    if output not in known:
        raise ValueError(f"Unknown output signal: {output!r}")

    available = set(variables) | {"0", "1"}
    pending = normalized[:]
    ordered = []
    while pending:
        ready = [g for g in pending if all(s in available for s in g["inputs"])]
        if not ready:
            raise ValueError("Circuit contains a feedback loop; only combinational circuits are allowed.")
        for gate in ready:
            ordered.append(gate)
            available.add(gate["output"])
            pending.remove(gate)
    return variables, ordered, output


def evaluate_circuit(ordered_gates, output, values):
    """Evaluate one assignment using the topologically sorted gates."""
    signals = dict(values)
    signals.update({"0": 0, "1": 1})
    for gate in ordered_gates:
        bits = [signals[name] for name in gate["inputs"]]
        kind = gate["type"]
        if kind in {"AND", "NAND"}:
            value = int(all(bits))
        elif kind in {"OR", "NOR"}:
            value = int(any(bits))
        elif kind in {"XOR", "XNOR"}:
            value = sum(bits) % 2
        else:  # BUF or NOT
            value = bits[0]
        if kind in {"NOT", "NAND", "NOR", "XNOR"}:
            value = 1 - value
        signals[gate["output"]] = value
    return signals[output]


def circuit_on_set(data):
    """Convert graph input into the same ON-set representation as SOP input."""
    variables, gates, output = validate_circuit(data)
    on_set = {i for i in range(2 ** len(variables))
              if evaluate_circuit(gates, output, input_values(i, variables))}
    return variables, on_set


def make_minterm(index, variable_names):
    """Make one canonical SOP term, such as a'bc."""
    bits = format(index, f"0{len(variable_names)}b")
    parts = []

    for bit, variable in zip(bits, variable_names):
        parts.append(variable if bit == "1" else variable + "'")

    return (" * " if any(len(v) > 1 for v in variable_names) else "").join(parts)


def make_maxterm(index, variable_names):
    """Make one canonical POS term, such as (a' + b + c')."""
    bits = format(index, f"0{len(variable_names)}b")
    parts = []

    for bit, variable in zip(bits, variable_names):
        parts.append(variable if bit == "0" else variable + "'")

    return "(" + " + ".join(parts) + ")"


def canonical_sop(minterms, variable_names):
    if not minterms:
        return "0"

    terms = [
        make_minterm(index, variable_names)
        for index in sorted(minterms)
    ]
    return " + ".join(terms)


def canonical_pos(maxterms, variable_names):
    if not maxterms:
        return "1"

    terms = [
        make_maxterm(index, variable_names)
        for index in sorted(maxterms)
    ]
    return " . ".join(terms)



def combine_patterns(pattern1, pattern2):
    """
    Combine two patterns that differ in exactly one 0/1 position.
    A dash means that the variable is eliminated.
    """
    difference_count = 0
    combined = []

    for bit1, bit2 in zip(pattern1, pattern2):
        if bit1 == bit2:
            combined.append(bit1)
        elif bit1 != "-" and bit2 != "-":
            difference_count += 1
            combined.append("-")
        else:
            return None

    if difference_count == 1:
        return "".join(combined)

    return None


def find_prime_implicants(minterms, number_of_variables):
    """Find prime implicants for a set of minterms."""
    if not minterms:
        return []

    current = sorted(
        format(index, f"0{number_of_variables}b")
        for index in minterms
    )
    prime_implicants = set()

    while current:
        used_patterns = set()
        next_patterns = set()

        for first, second in combinations(current, 2):
            combined = combine_patterns(first, second)

            if combined is not None:
                used_patterns.add(first)
                used_patterns.add(second)
                next_patterns.add(combined)

        for pattern in current:
            if pattern not in used_patterns:
                prime_implicants.add(pattern)

        current = sorted(next_patterns)

    return sorted(prime_implicants)


def pattern_covers(pattern, minterm):
    """Check whether an implicant pattern covers a minterm."""
    bits = format(minterm, f"0{len(pattern)}b")

    return all(
        pattern_bit == "-" or pattern_bit == bit
        for pattern_bit, bit in zip(pattern, bits)
    )


def literal_count(pattern):
    """Count the literals in an implicant pattern."""
    return sum(bit != "-" for bit in pattern)


def find_essential_prime_implicants(prime_implicants, minterms):
    """Find PIs that are the only ones covering at least one minterm."""
    essential = set()

    for minterm in minterms:
        covering = [
            pattern
            for pattern in prime_implicants
            if pattern_covers(pattern, minterm)
        ]

        if len(covering) == 1:
            essential.add(covering[0])

    return sorted(essential)


def choose_minimum_cover(prime_implicants, minterms):
    """Find an exact minimum-literal cover; break ties by number of terms.

    Essential PIs are mandatory. For the remaining rows, branch on an uncovered
    minterm: every complete cover must choose one PI that covers that row.
    Prune branches whose current cost cannot improve the best complete cover.
    If the search budget is exceeded, raise an error rather than claim a
    heuristic result is an exact minimum.
    """
    if not minterms:
        return []
    minterms = set(minterms)
    patterns = sorted(set(prime_implicants))
    coverage = {p: {m for m in minterms if pattern_covers(p, m)} for p in patterns}
    choices = {m: [p for p in patterns if m in coverage[p]] for m in minterms}
    if any(not values for values in choices.values()):
        raise ValueError("Prime implicants do not cover the ON-set.")
    essential = frozenset(find_essential_prime_implicants(patterns, minterms))
    covered = set().union(*(coverage[p] for p in essential))
    best = list(patterns)  # All PIs together form a valid initial cover.
    best_score = (sum(literal_count(p) for p in best), len(best))
    visited = set()

    def search(selected, remaining, cost):
        nonlocal best, best_score
        if selected in visited:
            return
        visited.add(selected)
        if len(visited) > MAX_COVER_STATES:
            raise RuntimeError("Exact cover search limit reached. Use a smaller circuit "
                               "or deliberately increase MAX_COVER_STATES.")
        score = (cost, len(selected))
        if not remaining:
            if score < best_score:
                best, best_score = sorted(selected), score
            return
        if score >= best_score:
            return
        row = min(remaining, key=lambda m: (len(choices[m]), m))
        for pattern in choices[row]:
            search(selected | {pattern}, remaining - coverage[pattern],
                   cost + literal_count(pattern))

    search(essential, minterms - covered,
           sum(literal_count(p) for p in essential))
    return sorted(best)


# -----------------------------
# Expression formatting helpers
# -----------------------------
def pattern_to_product(pattern, variable_names):
    """Convert an implicant pattern to an SOP product term."""
    parts = []

    for bit, variable in zip(pattern, variable_names):
        if bit == "1":
            parts.append(variable)
        elif bit == "0":
            parts.append(variable + "'")

    return (" * " if any(len(v) > 1 for v in variable_names) else "").join(parts) if parts else "1"


def complement_product_to_clause(pattern, variable_names):
    """Apply De Morgan's law to make a POS clause from an SOP product."""
    parts = []

    for bit, variable in zip(pattern, variable_names):
        if bit == "1":
            parts.append(variable + "'")
        elif bit == "0":
            parts.append(variable)

    return "(" + " + ".join(parts) + ")" if parts else "0"


def format_sop(patterns, variable_names):
    if not patterns:
        return "0"

    terms = [
        pattern_to_product(pattern, variable_names)
        for pattern in patterns
    ]

    if "1" in terms:
        return "1"

    return " + ".join(terms)


def format_pos_from_complement_sop(patterns, variable_names):
    """Make F's POS by complementing a minimized SOP for F-bar."""
    if not patterns:
        return "1"

    clauses = [
        complement_product_to_clause(pattern, variable_names)
        for pattern in patterns
    ]

    if "0" in clauses:
        return "0"

    return " . ".join(clauses)





class LogicEngine:
    """Shared synthesis state for either input representation."""

    def __init__(self, variables, on_set):
        self.variables = validate_variables(variables)
        self.on_set = set(on_set)
        self.all_minterms = set(range(2 ** len(variables)))
        if not self.on_set <= self.all_minterms:
            raise ValueError("ON-set contains a row outside the input range.")
        self.off_set = self.all_minterms - self.on_set
        self._primes = {}
        self._covers = {}

    def primes(self, inverse=False):
        if inverse not in self._primes:
            rows = self.off_set if inverse else self.on_set
            self._primes[inverse] = find_prime_implicants(rows, len(self.variables))
        return self._primes[inverse]

    def cover(self, inverse=False):
        if inverse not in self._covers:
            rows = self.off_set if inverse else self.on_set
            self._covers[inverse] = choose_minimum_cover(self.primes(inverse), rows)
        return self._covers[inverse]

    def essential(self):
        return find_essential_prime_implicants(self.primes(), self.on_set)

    def evaluate_bits(self, raw):
        bits = re.sub(r"[\s,]+", "", raw)
        if len(bits) != len(self.variables) or any(b not in "01" for b in bits):
            raise ValueError(f"Enter exactly {len(self.variables)} binary digits.")
        return int(int(bits, 2) in self.on_set)


def result_text(engine, command):
    """Return the result of required operations 1 through 10."""
    v, on, off = engine.variables, engine.on_set, engine.off_set
    if command == "1":
        return "Canonical SOP of F: " + canonical_sop(on, v)
    if command == "2":
        return "Canonical POS of F: " + canonical_pos(off, v)
    if command == "3":
        return "Canonical SOP of F-bar: " + canonical_sop(off, v)
    if command == "4":
        return "Canonical POS of F-bar: " + canonical_pos(on, v)
    if command in {"5", "6"}:
        inverse = command == "6"
        cover = engine.cover(inverse)
        expression = (format_pos_from_complement_sop(cover, v) if inverse
                      else format_sop(cover, v))
        canonical_literals = len(off if inverse else on) * len(v)
        minimized_literals = sum(literal_count(p) for p in cover)
        form = "POS" if inverse else "SOP"
        return (f"Minimized {form} of F: {expression}\n"
                f"Canonical literals: {canonical_literals}\n"
                f"Minimized literals: {minimized_literals}\n"
                f"{form} literals saved: {canonical_literals - minimized_literals}")
    if command in {"7", "8"}:
        patterns = engine.primes() if command == "7" else engine.essential()
        label = "Prime implicants" if command == "7" else "Essential prime implicants"
        terms = [pattern_to_product(p, v) for p in patterns]
        return f"{label}: {', '.join(terms) if terms else '(none)'}\nCount: {len(patterns)}"
    if command == "9":
        return f"ON-set minterm count: {len(on)}\nIndices: {sorted(on)}"
    if command == "10":
        return f"OFF-set maxterm count: {len(off)}\nIndices: {sorted(off)}"
    raise ValueError("Expected an operation number from 1 through 10.")


def truth_table_text(engine):
    lines = [" ".join(engine.variables) + " | F (output)"]
    for index in sorted(engine.all_minterms):
        bits = format(index, f"0{len(engine.variables)}b")
        lines.append(" ".join(bits) + f" | {int(index in engine.on_set)}")
    return "\n".join(lines)


def export_csv(engine, filename):
    with Path(filename).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(engine.variables + ["F (output)"])
        for index in sorted(engine.all_minterms):
            bits = format(index, f"0{len(engine.variables)}b")
            writer.writerow([int(b) for b in bits] + [int(index in engine.on_set)])


def structural_verilog(engine):
    """Generate primitive gates; safe port names prevent all name collisions.

    User input names are mapped to in_0, in_1, ... in their original order.
    The module output remains F, even when an original input is named F.
    """
    patterns = engine.cover()
    ports = [f"in_{i}" for i in range(len(engine.variables))]
    lines = ["// Automatically generated minimized SOP circuit."]
    lines += [f"// {port} = original input {name}"
              for port, name in zip(ports, engine.variables)]
    lines += ["module logic_function (",
              ",\n".join([f"    input wire {p}" for p in ports] + ["    output wire F"]),
              ");", ""]
    complemented = [i for i in range(len(ports)) if any(p[i] == "0" for p in patterns)]
    lines += [f"wire neg_{i};" for i in complemented]
    lines += [f"wire term_{i};" for i in range(len(patterns))]
    lines += [f"not g_not_{i} (neg_{i}, {ports[i]});" for i in complemented]
    for index, pattern in enumerate(patterns):
        literals = [ports[i] if bit == "1" else f"neg_{i}"
                    for i, bit in enumerate(pattern) if bit != "-"]
        if len(literals) <= 1:
            source = literals[0] if literals else "1'b1"
            lines.append(f"buf g_term_{index} (term_{index}, {source});")
        else:
            lines.append(f"and g_term_{index} (term_{index}, {', '.join(literals)});")
    if not patterns:
        lines.append("buf g_output (F, 1'b0);")
    elif len(patterns) == 1:
        lines.append("buf g_output (F, term_0);")
    else:
        terms = ", ".join(f"term_{i}" for i in range(len(patterns)))
        lines.append(f"or g_output (F, {terms});")
    lines += ["", "endmodule", ""]
    return "\n".join(lines)


def verilog_testbench(engine):
    """Check every output against the original input's truth table.

    Simulation-only testbench. Compile as SystemVerilog with Icarus -g2012
    for the $fatal failure exit; the generated circuit itself is Verilog.
    """
    width = len(engine.variables)
    connections = [f".in_{i}(stimulus[{width - 1 - i}])" for i in range(width)]
    connections.append(".F(F)")
    lines = ["`timescale 1ns/1ps", "module tb_logic_function;",
             f"reg [{width - 1}:0] stimulus;", "wire F;", "integer errors;",
             "logic_function dut (" + ", ".join(connections) + ");",
             "initial begin", "    errors = 0;",
             '    $dumpfile("logic_function.vcd");',
             "    $dumpvars(0, tb_logic_function);"]
    for index in sorted(engine.all_minterms):
        expected = int(index in engine.on_set)
        bits = format(index, f"0{width}b")
        lines += [f"    stimulus = {width}'b{bits}; #1;",
                  f"    if (F !== 1'b{expected}) begin",
                  '        $display("FAIL input=%b expected=%b actual=%b",'
                  f" stimulus, 1'b{expected}, F);",
                  "        errors = errors + 1;", "    end"]
    lines += ["    if (errors != 0)",
              '        $fatal(1, "FAIL: %0d mismatches", errors);',
              f'    $display("PASS: all {2 ** width} input combinations matched.");',
              "    $finish;", "end", "endmodule", ""]
    return "\n".join(lines)


def ask_path(prompt, default, suffix):
    text = input(f"{prompt} [{default}]: ").strip().strip('"') or default
    path = Path(text)
    if path.suffix.lower() != suffix:
        path = Path(str(path) + suffix)
    return path


def load_engine():
    while True:
        print("\nINPUT METHOD\n1. Enter an SOP expression\n2. Load a circuit JSON file\n0. Exit")
        choice = input("Choose: ").strip()
        try:
            if choice == "0":
                return None
            if choice == "1":
                raw = input("One-letter variables, in order (example a,b,c): ")
                variables = [name.strip() for name in raw.split(",")]
                validate_variables(variables, single_letter=True)
                expression = input("SOP (example ab + c'): ")
                return LogicEngine(variables, sop_on_set(variables, expression))
            if choice == "2":
                path = input("Circuit JSON filename: ").strip().strip('"')
                with Path(path).open(encoding="utf-8-sig") as stream:
                    data = json.load(stream)
                variables, on_set = circuit_on_set(data)
                return LogicEngine(variables, on_set)
            print("Choose 1, 2, or 0.")
        except (ValueError, OSError) as error:
            print(f"Input error: {error}")


MENU = """
REQUIRED OPERATIONS
 1. Canonical SOP of F              2. Canonical POS of F
 3. Canonical SOP of F-bar          4. Canonical POS of F-bar
 5. Literal-minimized SOP           6. Literal-minimized POS
 7. Prime implicants and count      8. Essential prime implicants and count
 9. ON-set minterms and count      10. OFF-set maxterms and count
11. Custom #1: evaluate F          12. Custom #2: export truth-table CSV

ADDITIONAL COMMANDS
 a. Display results 1-10            t. Display truth table
 v. Export structural Verilog      b. Export self-checking testbench
 r. Export text report             n. Load a new function
 0. Exit
"""


def main():
    print("EC551 Logic Synthesis Engine")
    print(f"Single-output circuits; 1-{MAX_INPUTS} inputs; exact literal minimization.")
    engine = load_engine()
    while engine is not None:
        print(f"\nLoaded inputs (MSB first): {', '.join(engine.variables)}")
        print(MENU)
        command = input("Command: ").strip().lower()
        try:
            if command == "0":
                break
            if command == "n":
                engine = load_engine()
            elif command in {str(i) for i in range(1, 11)}:
                print(result_text(engine, command))
            elif command == "a":
                for i in range(1, 11):
                    print("\n" + result_text(engine, str(i)))
            elif command == "t":
                print(truth_table_text(engine))
            elif command == "11":
                raw = input(f"Bits in {engine.variables} order: ")
                print("F =", engine.evaluate_bits(raw))
            elif command == "12":
                path = ask_path("CSV filename", "truth_table.csv", ".csv")
                export_csv(engine, path)
                print(f"Saved {path.resolve()}")
            elif command in {"v", "b", "r"}:
                if command == "v":
                    path = ask_path("Verilog filename", "logic_function.v", ".v")
                    text = structural_verilog(engine)
                elif command == "b":
                    path = ask_path("Testbench filename", "tb_logic_function.v", ".v")
                    text = verilog_testbench(engine)
                else:
                    path = ask_path("Report filename", "logic_report.txt", ".txt")
                    text = truth_table_text(engine) + "\n\n" + "\n\n".join(
                        result_text(engine, str(i)) for i in range(1, 11))
                path.write_text(text, encoding="utf-8")
                print(f"Saved {path.resolve()}")
            else:
                print("Unknown command. Choose one from the menu.")
        except (ValueError, OSError, RuntimeError) as error:
            print(f"Error: {error}")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nExiting.")
