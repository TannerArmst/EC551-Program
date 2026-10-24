# EC551-Program

# EC551-Program
# EC551 Programming Assignment 1: Logic Synthesis Engine

**Course:** EC551 - Advanced Digital Design with Verilog and FPGAs, Fall 2026  
**Instructor:** Prof. Douglas Densmore  
**Team members:** Tanner Armstard and Francis Liri  
**FPGA board:** Digilent Nexys3 with Xilinx Spartan-6 XC6SLX16 FPGA  
**FPGA toolchain:** Xilinx ISE Design Suite 14.7 WebPACK (legacy Xilinx toolchain)  
**Programming utility:** Xilinx iMPACT

## Project overview

This project implements a single-output combinational logic synthesis engine in Python. The program accepts either a Boolean Sum-of-Products (SOP) expression or a graph-based circuit described in a JSON file.

Both input methods are converted into an ordered input list and an ON-set. The engine computes canonical forms, minimizes SOP and POS representations, reports logic metrics, and automatically generates structural Verilog using primitive gates. It also generates a self-checking Verilog testbench.

The generated circuit is intended to be synthesized and implemented on an FPGA, with physical inputs and outputs connected through a board-specific wrapper and pin constraints.

## Features

| Command | Operation |
| --- | --- |
| `1` | Canonical SOP of F |
| `2` | Canonical POS of F |
| `3` | Canonical SOP of the complement of F |
| `4` | Canonical POS of the complement of F |
| `5` | Literal-minimized SOP and number of literals saved |
| `6` | Literal-minimized POS and number of literals saved |
| `7` | Prime implicants and their count |
| `8` | Essential prime implicants and their count |
| `9` | ON-set minterm count and indices |
| `10` | OFF-set maxterm count and indices |
| `11` | Custom command 1: evaluate F for an entered input assignment |
| `12` | Custom command 2: export the truth table to CSV |
| `a` | Display results for operations 1-10 |
| `t` | Display the truth table |
| `v` | Export structural Verilog |
| `b` | Export a self-checking Verilog testbench |
| `r` | Export a text report |
| `n` | Load another function |
| `0` | Exit |

## Repository structure

The supplied software package has this structure:

```text
.
├── README.md
├── logic_synthesis.py
├── test_logic_synthesis.py
└── examples/
    ├── example_circuit.json
    ├── logic_function.v
    └── tb_logic_function.v
```

The files under `examples/` implement the example function `ab+c'`. Exports created during an interactive session are saved to the entered paths, or to the current working directory when using the default filenames.

**Hardware files to add before the hardware demo:** the board wrapper, pin constraints, and any project scripts needed to reproduce implementation. Update this folder listing and the hardware instructions when those files exist.

## Requirements and launch

- **Python 3.9 or newer** runs the logic-synthesis program. No third-party Python packages are required.
- **Icarus Verilog** is optional and can compile and simulate the generated Verilog/testbench (`iverilog` and `vvp`).
- **Xilinx ISE Design Suite 14.7 WebPACK** is used to synthesize and implement designs for the Nexys3's Spartan-6 FPGA and generate a bitstream.
- **Xilinx iMPACT**, included with the ISE flow, is used to program the board over its USB-JTAG connection.

Open a terminal in the repository directory and run:

```bash
python logic_synthesis.py
```

On Windows, `py logic_synthesis.py` can be used if the Python launcher is installed. Python requires no separate compilation step.

## SOP input example

Choose input method `1`, then enter:

```text
Variables: a,b,c
Expression: ab+c'
```

Enter only the values after the labels when responding to the prompts. SOP syntax uses adjacency for AND, `+` for OR, and a straight apostrophe for NOT. Input names must be single ASCII letters. Constants `0` and `1` are accepted as whole product terms.

The first listed variable is the most significant bit. With `a,b,c`, minterm index 5 represents `a=1, b=0, c=1`.

Enter command `a` to display all ten standard results. Expected results include:

| Result | Expected value |
| --- | --- |
| Minimized SOP | `c' + ab` |
| Minimized POS | `(b + c') . (a + c')` |
| Prime implicants / essential prime implicants | 2 / 2 |
| ON-set | `{0, 2, 4, 6, 7}` |
| OFF-set | `{1, 3, 5}` |
| SOP literals saved | 12 |
| POS literals saved | 5 |

For command `11`, assignment `0,0,1` produces `F=0`, while `1,1,1` produces `F=1`. Equivalent expressions may list their terms in a different order.

## Graph-based circuit input

Choose input method `2` and enter:

```text
examples/example_circuit.json
```

A circuit file describes primary inputs, gates, signal connections, and one output:

```json
{
  "inputs": ["a", "b", "c"],
  "gates": [
    {"type": "AND", "inputs": ["a", "b"], "output": "n1"},
    {"type": "NOT", "inputs": ["c"], "output": "n2"},
    {"type": "OR", "inputs": ["n1", "n2"], "output": "F"}
  ],
  "output": "F"
}
```

Supported gates are AND, OR, NOT, BUF, NAND, NOR, XOR, and XNOR. NOT and BUF require one input; the other gates require at least two. Multi-input XOR computes odd parity, and XNOR complements that result. String signals `"0"` and `"1"` represent constants.

Gate entries may appear in any order. The program validates signal references and drivers, then orders the gates by their dependencies. Undefined signals, duplicate drivers, invalid gate inputs, and feedback loops are rejected. Graph input names may contain multiple characters using ASCII identifier syntax.

## Architecture and algorithms

1. **Input processing:** `sop_on_set` parses SOP expressions. `validate_circuit`, `evaluate_circuit`, and `circuit_on_set` process JSON graphs. Both paths produce the same truth-table representation.
2. **Shared state:** `LogicEngine` stores input order, the ON-set, the OFF-set, and cached prime-implicant and minimum-cover results.
3. **Canonical forms:** ON-set rows produce canonical SOP minterms; OFF-set rows produce canonical POS maxterms. Swapping the sets gives the complement's forms.
4. **Prime implicants:** Quine-McCluskey repeatedly combines compatible binary patterns that differ in exactly one fixed bit. A dash represents an eliminated literal. Patterns that cannot expand are prime implicants.
5. **Minimum cover:** Essential prime implicants are included first. A recursive exact search selects additional PIs, minimizing total literal count first and term count second. It skips repeated selections and prunes branches that cannot improve the best complete result.
6. **POS minimization:** The engine minimizes SOP for the complement of F, then applies De Morgan's law to construct POS for F.
7. **Verilog generation:** The selected SOP is implemented with NOT, AND, OR, and BUF primitives. Complemented inputs are shared between product terms.
8. **Verification generation:** The testbench checks every binary input combination against the original ON-set.

## Generate and simulate Verilog

After loading a function:

1. Enter `v` and press Enter at the filename prompt to generate `logic_function.v`.
2. Enter `b` and press Enter to generate `tb_logic_function.v`.
3. With Icarus Verilog installed and available on PATH, run:

```bash
iverilog -g2012 -s tb_logic_function -o sim.vvp logic_function.v tb_logic_function.v
vvp sim.vvp
```

A successful three-input simulation reports:

```text
PASS: all 8 input combinations matched.
```

The testbench produces `logic_function.vcd` for waveform viewing. Any mismatch, including an unknown output, triggers a failing simulation. Regenerate both files after changing the function. The testbench is simulation-only; `logic_function.v` is the generated circuit intended for synthesis.

Generated inputs are named `in_0`, `in_1`, etc., in the declared variable order, and the output is named `F`. For `a,b,c`, the mapping is `a → in_0`, `b → in_1`, `c → in_2`. Comments in the generated file record this mapping.

## Testing and current status

Run the included Python tests from the repository directory:

```bash
python -m unittest -v
```

The suite checks all 256 three-input Boolean functions against an independent minimization reference, selected four-input cases, SOP parsing, graph evaluation and validation, exports, and command interaction.

| Verification stage | Current documented status |
| --- | --- |
| Python functional checks in the development environment | 9 test methods passed; 1 optional HDL test skipped |
| HDL compilation and simulation | Not yet verified in the documented development environment; Icarus Verilog was unavailable |
| FPGA synthesis and implementation | Not yet documented |
| Live FPGA input/output verification | Not yet documented |

Update this table with your actual local and hardware results. Include the tool version, test function, and observed pass/fail result. The presence of a generated testbench does not establish that simulation has passed.

## FPGA implementation

**Complete this section for the actual board before presenting the hardware demo.**

- Board: Digilent Nexys3.
- FPGA: Xilinx Spartan-6 XC6SLX16 (package CSG324).
- Synthesis and implementation: Xilinx ISE Design Suite 14.7 WebPACK.
- Programming: Xilinx iMPACT over the board's USB-JTAG interface.
- Wrapper filename and top module: add the board-specific top-level wrapper and name it here.
- Constraints filename: add the Nexys3 UCF constraints file and name it here.
- Input mapping: assign selected Nexys3 switches/buttons to `in_0`, `in_1`, etc., in the declared variable order.
- Output mapping: assign `F` to a Nexys3 LED or other intended output.

Implementation procedure:

1. In ISE 14.7, create a project for the Nexys3's Spartan-6 XC6SLX16 device (confirm the exact speed grade and package shown for your board revision).
2. Add the generated `logic_function.v`, a Nexys3 top-level wrapper, and the board UCF constraints file. Select the wrapper as the top module.
3. Connect wrapper ports to the generated `in_0`, `in_1`, etc., and `F` ports. Use the Nexys3 reference manual/master UCF to confirm physical pin assignments; do not guess pin numbers.
4. Run Synthesize, Implement Design, and Generate Programming File in ISE.
5. Connect the Nexys3 by USB-JTAG and use iMPACT to identify the FPGA and program the generated `.bit` file.
6. Apply switch/button combinations and compare the observed output with the exported truth table.

The board-specific wrapper, UCF file, successful ISE implementation, and live hardware results still need to be added when completed. The Python program and its Verilog generator alone do not provide those board-specific files.

## Limitations

- One output and 1-8 primary inputs.
- Fully specified combinational functions; no sequential logic or external don't-care set.
- SOP entry accepts single-letter variables and SOP syntax, rather than arbitrary multilevel expressions.
- Exact cover search raises an error after 200,000 distinct search states. It does not return an unfinished solution as a proven optimum.
- Truth-table enumeration and exact minimization can become expensive as the input grows.
- Structural Verilog is generated from the minimized SOP, even when the minimized POS has a lower literal count.
- Minimum literal count does not guarantee minimum FPGA LUT usage or physical delay.

## AI-use acknowledgment

OpenAI ChatGPT was used to help debug the code and explain how to use the program’s functions and commands. 

## Toolchain references

- [Nexys 3 Reference Manual (Digilent)](https://digilent.com/reference/programmable-logic/nexys-3/reference-manual)
- [Xilinx ISE Design Suite 14.7 download and device support (AMD)](https://www.amd.com/en/support/downloads/adaptive-socs-and-fpgas/legacy-ise/v2012_4---14_7.html)

