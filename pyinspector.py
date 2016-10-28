'''
Custom Python Debugger developed by Nick Phillips
Intended to
1) Get a history log/trace for each variable in the program, for every step
   in the given program's execution
2) Perform tests on the specified function using specified test cases

I've taken inspiration from Online Python Tutor, by Philip Guo
Website:    http://www.pythontutor.com/
GitHub:     https://github.com/pgbovine/OnlinePythonTutor/

I strongly recommend using this site (in conjunction with mine :) ), as it
goes into more detail concerning the structure of Python frames and
object pointer references.

The key function is 'trace', which returns the JSON list of all traced
variables with their history {trace_out}
given an input string of the code {code_in}
'''
import sys
import traceback
import logging
import ast
import bdb
import copy
import gc
import inspect
import timeit
import types

from StringIO import StringIO
from itertools import chain

DEFAULT_VARS = set(('__builtins__', '__doc__', '__name__', '__package__'))

# Threshold to prevent infinite loops
MAX_STEPS = 500

class PyInspector(bdb.Bdb):
    def __init__(self, code_str_in, extra_line_data={}, test_data={"tests":[],"func_name":None}):
        bdb.Bdb.__init__(self)
        # Additional line data such as expression trees (only able to get from
        # AST parser library)
        self.extra_line_data = extra_line_data

        self.has_errors = False
        self.errors = []

        # ==== Testing ==== #
        self.test_results = []
        self.all_tests_passed = False
        self.testing = False
        self.progress = {"num_steps": None, "num_vars" : None}
        # ================= #

        self.debug = False
        self.exec_step_num = 0
        self.lineno = 0

        self.finished_tracing = False

        # Stores meta data for all steps of execution
        self.exec_steps = []
        self.current_step = {}
        # Keep track of scope for variables / execution steps
        self.scope_stack = ["<global>"]

        self.trace_out = []
        self.trace_history = None

        # Dictionary of variables (local and global) and their trace history
        # Trace history is indexed by execution step
        self.var_dict = {}

        # List of linenumbers, indexed by execution step
        self.exec_step_linenums = []

        # Idea is this:
        # Each variable trace represented by JSON
        # Each variable has a name and trace list
        # In theory, the trace list *should* be the same length as the number of
        # steps in execution

        self.code_output = None
        self.time_taken = None

        # Create code object from input code string
        try:
            code_in = compile(code_str_in, "<string>", mode="exec")
        except SyntaxError as e:
            self.add_error(e.args[0], e.lineno,0,e.lineno,999)
            return
        except Exception as e:
            self.add_error(str(e), 0,0,0,0)
            return

        # Set local and global namespaces
        self.global_vars = {"__name__" : "__main__"}
        self.local_vars = self.global_vars

        # Catch stdout to capture code output
        sys.stdout = mystdout = StringIO()
        # Debug IO object to capture debug output
        self.debug_out = StringIO()
        # Backup debugger, for surgical / quick debugging
        self.force_debug = StringIO()
        try:
            self.run(code_in, self.global_vars, self.local_vars)
            # Reset stdout
            sys.stdout = sys.__stdout__
        except NameError as e:
            # Reset stdout
            sys.stdout = sys.__stdout__
            pass

        except Exception as e:
            # Reset stdout
            sys.stdout = sys.__stdout__
            traceback.print_exc()
            self.add_error(str(e), self.lineno, 0, self.lineno, 999)
            print("Error in PyInspector base code: " + str(e))

        self.code_output = mystdout.getvalue()

        # Set variable trace history - this will be returned to the user
        self.trace_history = self.package_vars()

        #garbage collection
        gc.collect()

        # Only get run time if no errors are reported
        if not self.has_errors:
            sys.stdout = StringIO()
            try:
                # Get time taken to compute (convert to milliseconds)
                self.time_taken = (timeit.timeit(code_str_in, number=10) / 10.0) * 1000
            except:
                # Let the tracing handle exception reporting
                pass

            # Run code through each test
            self.all_tests_passed = True
            tests = test_data["tests"]
            self.target_func_name = test_data["func_name"]
            self.testing = True
            for self.test_index in xrange(0, len(tests)):
                # ast.literal_eval transforms a list in string form to list form
                inputs = ast.literal_eval(tests[self.test_index]["inputs"])
                outputs = ast.literal_eval(tests[self.test_index]["outputs"])

                self.current_inputs = inputs
                self.current_outputs = outputs

                # Run code with appended test assignment and variables
                test_code = "\n" + self.target_func_name+"("
                for input_data in inputs:
                    test_code += self.get_test_input_assignment(input_data) + ","
                # Remove last appended comma
                test_code = test_code[:-1] + ")\n"
                self.debug_out.write("TEST CODE:\n"+code_str_in+test_code+"\n")
                try:
                    # Reset scope stack, var names and step num
                    self.exec_step_num = 0
                    self.scope_stack = []
                    self.var_dict = {}

                    # Now perform the test using the generated globals and locals
                    self.run(test_code, self.global_vars, self.local_vars)

                    # Only save progress for the first test data
                    if self.test_index == 0:
                        self.progress["num_steps"] = self.exec_step_num
                        self.progress["num_vars"] = len(self.var_dict)

                except KeyError as e:
                    sys.stdout = sys.__stdout__
                    print("KeyError in test case")
                    break

                except NameError as e:
                    sys.stdout = sys.__stdout__
                    print("NameError in test case")
                    break

                except Exception as e:
                    sys.stdout = sys.__stdout__
                    print("Exception in test case: " + str(e))
                    break

        sys.stdout = sys.__stdout__
        print(self.force_debug.getvalue())

        if self.debug:
            logging.debug(self.debug_out.getvalue())

    # Strip the given var dict of the default in-built vars
    def get_filtered_vars(self, old_vars):
        new_vars = {}
        for (k, v) in old_vars.items():
            if k not in DEFAULT_VARS:
                new_vars[k] = v
        return new_vars

    # Returns 4 values ...
    # trace_history:       Trace history of all variables, as a Python dict
    # self.exec_steps:   list of linenums indexed by execution step
    # code_output:          The console output for the given program
    # time_taken:           The time taken for the given program to execute
    def get_trace_vals(self):
        return self.trace_history, self.exec_steps, self.code_output, self.time_taken

    # Helper function returning a dict representing an error
    # Cloned from TreeChecker class
    #
    # text              -> Descriptive text accompanying the issue
    # s_l               -> Starting line of the issue
    # s_c               -> Starting column of the issue
    # e_l               -> Ending line of the issue
    # e_c               -> Ending column of the issue
    # repl              -> Replacement code (optional)
    def add_error(self, text, s_l, s_c, e_l, e_c, repl=None):
        self.has_errors = True
        out = {
            "issue_type" : "error",
            "text" : text,
            "s_l" : s_l,
            "s_c" : s_c,
            "e_l" : e_l,
            "e_c" : e_c,
            "repl" : repl,
        }
        self.errors.append(out)

    # Packages the var_dicts into a list of inidividual dicts in the form:
    # [{"name" : "x", "trace" : ['unassigned','1','2']}]
    def package_vars(self):
        out = {}
        for (k, v) in self.var_dict.iteritems():
            # Ensure that all variables are padded with values on the end
            last_val = v[-1]
            for i in range(len(v), self.exec_step_num):
                v.append(last_val)

            # Obtain scope from name, ignore last item as the actual name
            scope_stack = k.split(':')
            var_name = scope_stack.pop()

            # Keyed by variable name (with scope)
            out[k] = {
                "var_name" : var_name,
                "scope" : scope_stack,
                "trace" : v,
            }
        return out

    def evaluate_node(self, node):
        if node["type"] == "num":
            n = node["disp"]
            node["eval_value"] = float(n) if '.' in n else int(n)
        elif node["type"] == "variable":
            # First check if variable is reserved - e.g. True, False
            if node["disp"] == "True":
                node["eval_value"] = True
            elif node["disp"] == "False":
                node["eval_value"] = False
            else: # Variable is not reserved
                # This is where the cool stuff happens - assigning trace variables!
                for variable in self.current_step["active_vars"]:
                    if node["disp"] == variable["var_id"].split(':')[-1]:
                        node["eval_value"] = variable["var_value"]
        elif node["type"] == "list":
            node["eval_value"] = eval(node["disp"], self.global_vars, self.local_vars)
        elif node["type"] == "subscript":
            node["eval_value"] = eval(node["disp"], self.global_vars, self.local_vars)
        elif node["type"] == "attribute":
            node["eval_value"] = eval(node["disp"], self.global_vars, self.local_vars)
        elif node["type"] == "tuple":
            node["eval_value"] = eval(node["disp"], self.global_vars, self.local_vars)
        elif node["type"] == "string":
            node["eval_value"] = node["disp"]
        elif node["type"] == "binop":
            child_a = self.evaluate_node(node["children"][0])
            child_b = self.evaluate_node(node["children"][1])
            if child_a == None or child_b == None:
                node["eval_value"] = node["children"][0]["disp"] + node["disp"] + node["children"][1]["disp"]
            else:
                if node["disp"] == "+":
                    if type(child_a) is str or type(child_b) is str:
                        node["eval_value"] = (str(child_a) + str(child_b))
                    else:
                        node["eval_value"] = (child_a + child_b)
                elif node["disp"] == "-":
                    node["eval_value"] = (child_a - child_b)
                elif node["disp"] == "*":
                    node["eval_value"] = (child_a * child_b)
                elif node["disp"] == "/":
                    if child_b == 0:
                        self.add_error("Error: can't divide by zero", self.lineno, 0, self.lineno, 999)
                        raise ZeroDivisionError()
                    else:
                        node["eval_value"] = (child_a / child_b)
                elif node["disp"] == "//":
                    node["eval_value"] = (child_a // child_b)
                elif node["disp"] == "%":
                    if child_b == 0:
                        self.add_error("Error: can't modulo by zero", self.lineno, 0, self.lineno, 999)
                        raise ZeroDivisionError()
                    else:
                        node["eval_value"] = (child_a % child_b)
                elif node["disp"] == "**":
                    node["eval_value"] = (child_a ** child_b)
                elif node["disp"] == "<<":
                    node["eval_value"] = (child_a << child_b)
                elif node["disp"] == ">>":
                    node["eval_value"] = (child_a >> child_b)
                elif node["disp"] == "|":
                    node["eval_value"] = (child_a | child_b)
                elif node["disp"] == "^":
                    node["eval_value"] = (child_a ^ child_b)
                elif node["disp"] == "&":
                    node["eval_value"] = (child_a & child_b)
        elif node["type"] == "boolop":
            child_a = self.evaluate_node(node["children"][0])
            child_b = self.evaluate_node(node["children"][1])
            if node["disp"] == "and":
                node["eval_value"] = (child_a and child_b)
            elif node["disp"] == "or":
                node["eval_value"] = (child_a or child_b)
        elif node["type"] == "compare":
            child_a = self.evaluate_node(node["children"][0])
            child_b = self.evaluate_node(node["children"][1])
            if child_a == None or child_b == None:
                node["eval_value"] = node["children"][0]["disp"] + node["disp"] + node["children"][1]["disp"]
            else:
                if node["disp"] == "==":
                    node["eval_value"] = (child_a == child_b)
                elif node["disp"] == "!=":
                    node["eval_value"] = (child_a != child_b)
                elif node["disp"] == "<":
                    node["eval_value"] = (child_a < child_b)
                elif node["disp"] == "<=":
                    node["eval_value"] = (child_a <= child_b)
                elif node["disp"] == ">":
                    node["eval_value"] = (child_a > child_b)
                elif node["disp"] == ">=":
                    node["eval_value"] = (child_a >= child_b)
                elif node["disp"] == "is":
                    node["eval_value"] = (child_a is child_b)
                elif node["disp"] == "is not":
                    node["eval_value"] = (child_a is not child_b)
                elif node["disp"] == "in":
                    node["eval_value"] = (child_a in child_b)
                elif node["disp"] == "not in":
                    node["eval_value"] = (child_a not in child_b)
        # Functions
        elif node["type"] == "function":
            # Check for safe, built-in functions like len() and assign
            if node["disp"] == "len":
                node["eval_value"] = len(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "abs":
                node["eval_value"] = abs(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "any":
                node["eval_value"] = any(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "bin":
                node["eval_value"] = bin(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "chr":
                node["eval_value"] = chr(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "float":
                node["eval_value"] = float(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "hex":
                node["eval_value"] = hex(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "int":
                node["eval_value"] = int(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "max":
                node["eval_value"] = max(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "min":
                node["eval_value"] = min(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "ord":
                node["eval_value"] = ord(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "str":
                node["eval_value"] = str(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "sum":
                node["eval_value"] = sum(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "list":
                node["eval_value"] = list(self.evaluate_node(node["children"][0]))
            elif node["disp"] == "pow":
                node["eval_value"] = pow(self.evaluate_node(node["children"][0]),self.evaluate_node(node["children"][1]))
            else:
                # Check if the function call is an attribute
                attrs = node["disp"].split(".")
                if len(attrs) > 1:
                    # Check for builtin function methods
                    if attrs[-1] in ["index", "count", "lower", "upper", "join"] :
                        node["eval_value"] = eval(node["code"][0], self.global_vars, self.local_vars)


        # Return statement
        elif node["type"] == "return":
            node["eval_value"] = "returned with value " + str(self.evaluate_node(node["children"][0]))

        # Assignments
        elif node["type"] == "assignment":
            left_str = ""
            for i in range(len(node["children"])-1):
                left_str += str(node["children"][i]["disp"]) + ","
            node["eval_value"] = left_str[:-1] + " assigned to " + str(self.evaluate_node(node["children"][-1]))

        return node["eval_value"]

    def evaluate_and_assign_variables(self, extra_line_data):
        # Deepcopy allows the dicts and sub-dicts to be copied by value
        line_data = copy.deepcopy(extra_line_data)
        self.evaluate_node(line_data)
        return line_data

    def process_vars(self, frame):
        self.global_vars = frame.f_globals
        self.local_vars = frame.f_locals

        # Increment execution step and append to execution linenums list
        self.exec_step_num += 1

        current_line = frame.f_lineno
        self.lineno = current_line
        self.exec_step_linenums.append(current_line)

        global_vars = self.get_filtered_vars(frame.f_globals)
        local_vars = self.get_filtered_vars(frame.f_locals)
        caller_name = frame.f_code.co_name

        all_vars = dict(chain(global_vars.items(), local_vars.items()))

        # Active variables for current step in execution
        self.current_step["active_vars"] = []

        # Iterate through locals and globals, adding new vars to trace_out
        # For existing variables, update trace values
        for (varname, val) in all_vars.iteritems():
            # Add scope to variable name
            varname = ":".join(self.scope_stack) + ":" + varname

            # If variable refers to a function, just print '(function)'
            if hasattr(val, '__call__'):
                val = "FUNCTION"
            elif isinstance(val, types.ModuleType): # If value is a module, just put 'MODULE'
                val = "MODULE"
            elif isinstance(val, types.ClassType):
                val = "CLASS"
            elif isinstance(val, types.InstanceType):
                val = "INSTANCE"
            # New variable
            if varname not in self.var_dict.keys():
                self.var_dict[varname] = []
                for i in range(0, self.exec_step_num-1):
                    self.var_dict[varname].append("unassigned")
                self.var_dict[varname].append(str(val))
            # Existing variable
            else:
                last_val = self.var_dict[varname][-1]
                for i in range(len(self.var_dict[varname]), self.exec_step_num-1):
                    self.var_dict[varname].append(last_val)
                self.var_dict[varname].append(str(val))
            # Append variable to list for execution step
            var_data = {
                "var_id" : varname,
                "var_value" : val,
            }
            self.current_step["active_vars"].append(var_data)

        # If not testing, process extra line data, such as expressions, in order to show variables
        if not self.testing:
            self.current_step["extra_line_data"] = []
            if str(current_line) in self.extra_line_data:
                for line_data in self.extra_line_data[str(current_line)]:
                    # This evaluates expressions, assignments, etc. according to
                    # variable values at the current step.
                    evaluated_data = self.evaluate_and_assign_variables(line_data)
                    self.current_step["extra_line_data"].append(evaluated_data)

            # Process entry for step in execution
            self.current_step["line_num"] = current_line
            self.current_step["scope"] = self.scope_stack[:] # Copy by value, not reference
            # TODO: obtain info r.e. what is being returned / assigned / etc.
            self.current_step["data"] = {}

            step_copy = copy.deepcopy(self.current_step)
            # Add step to list of steps
            self.exec_steps.append(step_copy)
            # Flush current step object
            self.current_step = {}

        # If steps exceeds the max_steps threshold, then exit tracing
        if self.exec_step_num > MAX_STEPS:
            self.finished_tracing = True
            self.add_error("Your code has too many steps (> "+ str(MAX_STEPS) +")", current_line, 1, current_line, 999)
            # Force quit execution
            raise bdb.BdbQuit
            return

        # Debugging
        self.debug_out.write("CURRENT VAR_DICT:\n" + str(self.var_dict) + "\n")
        self.debug_out.write("LINE NUM: " + str(current_line) + "\n")
        self.debug_out.write("LISTING GLOBAL VARS IN FRAME\n" + str(global_vars) + "\n")
        self.debug_out.write("LISTING LOCAL VARS IN FRAME\n" + str(local_vars) + "\n")

    #============ Test Case Methods ==============#
    def get_test_input_assignment(self, input_data):
        input_val = input_data["value"]
        if input_data["type"] == "string":
            # Wrap strings in quotes
            input_val = "\"" + input_val + "\""
        return input_data["name"] + "=" + str(input_val)

    def get_test_output_value(self, output_data):
        output_val = output_data["value"]
        if output_data["type"] == "number":
            if '.' in output_val:
                # Float value
                output_val = float(output_val)
            else:
                # int value
                output_val = int(output_val)
        elif output_data["type"] == "list":
            output_val = ast.literal_eval(output_val)

        return output_val

    def set_test_result(self, value):
        output_data = []
        passed_test = True
        if isinstance(value, tuple):
            # More than one output from the function
            index = 0
            for tuple_val in value:
                expected_output = self.current_outputs[index]
                expected_val = self.get_test_output_value(expected_output)
                expected_type = expected_output["type"]

                # Get tuple_val type
                actual_type = None
                if type(tuple_val) is int or type(tuple_val) is float:
                    actual_type = "number"
                elif type(tuple_val) is str:
                    actual_type = "string"
                elif type(tuple_val) is list:
                    actual_type = "list"

                this_output_passed = expected_val == tuple_val

                passed_test &= this_output_passed

                output_data.append({
                    "expected_val" : expected_val,
                    "expected_type" : expected_type,
                    "actual_val" : tuple_val,
                    "actual_type" : actual_type,
                    "passed" : this_output_passed,
                })
                index += 1
        else:
            # Just one value
            expected_val = self.get_test_output_value(self.current_outputs[0])
            expected_type = self.current_outputs[0]["type"]
            # Get tuple_val type
            actual_type = None
            if type(value) is int or type(value) is float:
                actual_type = "number"
            elif type(value) is str:
                actual_type = "string"
            elif type(value) is list:
                actual_type = "list"

            this_output_passed = expected_val == value

            passed_test &= this_output_passed

            output_data.append({
                "expected_val" : str(expected_val),
                "expected_type" : expected_type,
                "actual_val" : str(value),
                "actual_type" : actual_type,
                "passed" : this_output_passed,
            })

        self.all_tests_passed &= passed_test
        self.test_results.append({
            "inputs" : self.current_inputs,
            "outputs" : output_data,
            "passed" : passed_test,
            "num_vars" : len(self.var_dict),
            "num_steps" : self.exec_step_num,
        })

    #============= In-Built Methods ==============#
    def user_call(self, frame, args):
        if "__all__" in frame.f_globals:
            self.set_step()
            return

        # Push name of function onto scope stack
        self.scope_stack.append(frame.f_code.co_name)

        self.current_step["type"] = "CALL"

        self.debug_out.write("\n--- FUNCTION CALL ---\n")
        self.process_vars(frame)
        self.set_step() # VERY IMPORTANT!

    def user_line(self, frame):
        if "__all__" in frame.f_globals:
            self.set_step()
            return

        self.current_step["type"] = "LINE"

        self.debug_out.write("\n------- LINE --------\n")
        # Maybe stack would be useful inside functions?
        #stack, curindx = self.get_stack(frame, None)
        self.process_vars(frame)
        # Continue to next line of code
        self.set_step() # VERY IMPORTANT!

    def user_return(self, frame, value):
        if "__all__" in frame.f_globals:
            self.set_step()
            return

        name = frame.f_code.co_name or "<unknown>"
        # Stop tracing if we have reached the end of the input file.
        if name == "<module>":
            # Skip tracing variables here
            self.set_continue()
            return

        # Pop head from scope stack
        self.scope_stack.pop()

        self.current_step["type"] = "RETURN"

        self.debug_out.write("\n----- RETURNING -----\n")
        self.debug_out.write("RETURNING FROM FUNCTION: " + str(name) + "\nWITH VALUE: " + str(value) + "\n")
        self.process_vars(frame)

        # If returning from test input function and in test_mode, set value
        # Checking if the calling frame's code object is not nested
        # This ensures the value obtained is accurate if the function is recursive
        if self.testing and name == self.target_func_name and frame.f_back.f_code.co_name == "<module>":
            self.set_test_result(value)
            # Finish debugging
            self.set_continue()

        self.set_step() # VERY IMPORTANT!

    def user_exception(self, frame, exception_info):
        if "__all__" in frame.f_globals:
            self.set_step()
            return

        name = frame.f_code.co_name or "<unknown>"

        # Add error to list of errors
        ex_type, err_text, traceback_obj = exception_info
        err_line = frame.f_lineno
        self.add_error(err_text, err_line, 1, err_line, 999)

        self.current_step["type"] = "EXCEPTION"

        # Debugging
        self.debug_out.write("\n----- EXCEPTION -----\n")
        self.debug_out.write("EXCEPTION FOUND IN: " + str(name) + "\nWITH: " + str(exception_info) + "\n")
        self.process_vars(frame)
        self.set_continue() # VERY IMPORTANT!

def test(filepath):
    with open (filepath, "r") as myfile:
        code_str = myfile.read()
    extra_l_d = {}
    test_d = {
            "tests": [],
            "func_name": None,
            }
    dbg = PyInspector(code_str, extra_l_d, test_d)
    trace_history, exec_steps, code_output, time_taken = dbg.get_trace_vals()
    print("=========== Variable Trace History ===========")
    for key, val in trace_history.iteritems():
        print(key)
        print(str(val) + "\n")
    print("\n=========== Execution Step State ===========")
    for n, exec_step in enumerate(exec_steps):
        print("\n=== Step " + str(n+1) + " ===")
        print("Line:\t" + str(exec_step["line_num"]))
        print("Scope:\t" + str(":".join(exec_step["scope"])))
        print("- Active Vars:")
        for v in exec_step["active_vars"]:
            print("\n"+v["var_id"])
            print(v["var_value"])

    print("\n=========== Efficiency Statistics ===========")
    print("Filepath:\t\t\t" + str(filepath))
    print("Execution time:\t\t\t" + str(time_taken) + " milliseconds")
    print("Number of steps in execution:\t" + str(len(exec_steps)))
    print("Number of variables used:\t" + str(len(trace_history)))
    #print(dbg.debug_out.getvalue())

if __name__ == "__main__":
    # Unit Test
    # Check command line arguments
    if len(sys.argv) == 1:
        #filepath = "code-examples/RedundantElseifComparison.py"
        filepath = "workspaces/examples-python/0/files/0_euclid.py"
        #filepath = "code-examples/SimpleCalculation.py"
    elif len(sys.argv) == 2:
        filepath = sys.argv[1]
    else:
        print("Error: too many arguments")
        sys.exit()

    test(filepath)
