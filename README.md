# pyinspector
Python code inspector which returns variable data at each step in execution.

This library was initially created for the CodeAssistant website [codeassistant.org](http://www.codeassistant.org).

## Usage

### Command Line
Gives analysis of variables at each step in program's execution

```bash
python pyinspector.py path/to/file.py
```

### Examples
See `examples` directory
```bash
python pyinspector.py examples/fibonacci.py
```

#### Example Command Line Output
```python
# myfile.py
j = 0
for i in range(3):
  j = j + (i * 2)
print(j)
```

```bash
> python pyinspector.py path/to/myfile.py

=========== Variable Trace History ===========
<global>:i
{'scope': ['<global>'], 'var_name': 'i', 'trace': ['unassigned', 'unassigned', '0', '0', '1', '1', '2', '2', '2']}

<global>:j
{'scope': ['<global>'], 'var_name': 'j', 'trace': ['unassigned', '0', '0', '0', '0', '2', '2', '6', '6']}


=========== Execution Step State ===========

=== Step 1 ===
Line:	1
Scope:	<global>
- Active Vars:

=== Step 2 ===
Line:	2
Scope:	<global>
- Active Vars:

<global>:j
0

=== Step 3 ===
Line:	3
Scope:	<global>
- Active Vars:

<global>:i
0

<global>:j
0

=== Step 4 ===
Line:	2
Scope:	<global>
- Active Vars:

<global>:i
0

<global>:j
0

=== Step 5 ===
Line:	3
Scope:	<global>
- Active Vars:

<global>:i
1

<global>:j
0

=== Step 6 ===
Line:	2
Scope:	<global>
- Active Vars:

<global>:i
1

<global>:j
2

=== Step 7 ===
Line:	3
Scope:	<global>
- Active Vars:

<global>:i
2

<global>:j
2

=== Step 8 ===
Line:	2
Scope:	<global>
- Active Vars:

<global>:i
2

<global>:j
6

=== Step 9 ===
Line:	4
Scope:	<global>
- Active Vars:

<global>:i
2

<global>:j
6

=========== Efficiency Statistics ===========
Filepath:			path/to/myfile.py
Execution time:			0.00388622283936 milliseconds
Number of steps in execution:	9
Number of variables used:	2
```

### Importing
Obtain code inspection objects and variables to analyse yourself.

```python
from pyinspector import PyInspector

filepath = "myfile.py"
with open (filepath, "r") as myfile:
  code_str = myfile.read()
pi = PyInspector(code_str)
trace_history, exec_steps, code_output, time_taken = pi.get_trace_vals()
```

## Config
`MAX_STEPS` is set to prevent the program from entering infinite loops. (500 by default)

## License
MIT

## Creator
Nick Phillips - [ntgphillips.co.uk](http://www.ntgphillips.co.uk)
