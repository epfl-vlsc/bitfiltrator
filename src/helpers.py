# author: Sahand Kashani <sahand.kashani@epfl.ch>

import json
import re
import subprocess
import typing
from pathlib import Path

import numpy as np


# Generic helper method to extract a bit slice from an integer.
def bits(
  input: int,
  idx_high: int,
  idx_low: int
) -> int:
  assert idx_high >= idx_low, f"Error: Invalid bit range {idx_high}:{idx_low}"
  # We left-shift the input by idx_low, then mask the bit pattern to isolate
  # the part we are interested in.
  shifted_input = input >> idx_low
  mask = (1 << (idx_high - idx_low + 1)) - 1
  res = shifted_input & mask
  return res

# Returns the number of bits between the 2 indices.
def width(
  idx_high: int,
  idx_low: int
) -> int:
  assert idx_high >= idx_low, f"Error: Expected idx_high >= idx_low"
  return idx_high - idx_low + 1

# Searches a string for a regex pattern. This function expects the search to succeed and throws
# an error if it is not the case. It avoids repetitive error handling in callers.
def regex_match(
  pattern: str,
  string: str
) -> re.Match:
  match = re.search(pattern, string)
  assert match is not None, f"Error: Expected \"{string}\" to match \"{pattern}\""
  return match

# Reads a json file.
def read_json(
  path: Path
) -> dict[str, typing.Any]:
  if path is not None:
    with open(path, "r") as f:
      return json.loads(f.read())

  return dict()

# Runs a tcl/python.
# - If a file path is provided for stdout and stderr, these are written to the
#   corresponding file. Otherwise stdout/stderr is discarded.
# - If a list of expected output files is provided, we test for their presence
#   after the python script runs to ensure execution was successful. If not, an
#   error is printed.
# - True is returned if all expected output files exist, and False otherwise. If
#   no outputs are expected, True is returned.
def run_script(
  script_path: Path,
  args: list[str],
  expected_output_paths: list[Path] = None,
  stdout_path: Path = None,
  stderr_path: Path = None,
  verbose: bool = False
) -> bool:
  # Programs are launched in /tmp to avoid polluting the target directory with auxiliary files (vivado journal files, etc.)
  tmp_dir = Path("/tmp")

  extension = script_path.suffix
  if extension == ".tcl":
    cmd = ["vivado", "-mode", "batch", "-source", script_path, "-notrace", "-tclargs", *args]
  elif extension == ".py":
    cmd = ["python3", script_path, *args]
  else:
    assert False, f"Error: Unknown file extension {extension} for script {script_path}"

  if expected_output_paths is None:
    done = False
  elif any((arg is None for arg in args)):
    done = True
  else:
    args_not_available = any((arg is None for arg in args))
    outputs_already_available = all((expected_output_path.exists() for expected_output_path in expected_output_paths))
    # We skip execution if any of the args are not available as vivado occasionally segfaults mid-execution
    # if it runs out of memory and our methods return None in such cases. We don't want to launch a future
    # step that depends on a previous artifact that is not available, so we skip execution in such cases and
    # the user will have to re-run this script until all artifacts are available.
    done = args_not_available or outputs_already_available

  # Run command only if results do not exist (otherwise it is duplicated work).
  if not done:
    if verbose:
      print(" ".join([str(x) for x in cmd]))

    res = subprocess.run(cmd, cwd=tmp_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if stdout_path is not None:
      with open(stdout_path, "w") as f:
        f.write(res.stdout.decode("utf-8"))

    if stderr_path is not None:
      with open(stderr_path, "w") as f:
        f.write(res.stderr.decode("utf-8"))

  if expected_output_paths is not None:
    # We are capturing the outputs and writing them to a file. The user
    # therefore will not easily see if a script (among those launched in the
    # large batch) has failed. We therefore print a succint message here so the
    # user can easily know that something failed.

    received_output_paths: list[Path] = list()
    for expected_output_path in expected_output_paths:
      if expected_output_path.exists():
        received_output_paths.append(expected_output_path)
      else:
        # There are Path objects in cmd, so we need to transform them to strings
        # before we can join them together.
        cmd_str = " ".join([str(x) for x in cmd])
        print(f'Warning: Failed to generate {expected_output_path} (cmd \"{cmd_str}\")')

    return received_output_paths == expected_output_paths

  return True

def is_binary_int(
  value: int
) -> bool:
  return (value == 0) or (value == 1)

def is_binary_str(
  value: str
) -> bool:
  for x in value:
    if not is_binary_int(int(x)):
      return False

  return True

# Converts numbers from the following "verilog" form:
#
#   64'h[0-9a-fA-F]{16}
#   64'b[0-9a-fA-F]{64}
#
# into a python binary string:
#
#   [01]{64}
def verilog_num_to_bin(vnum: str) -> str:
  pattern = r"(?P<num_bits>\d+)'(?P<base>[hb])(?P<value>[0-9a-fA-F]+)"
  match = regex_match(pattern, vnum)
  num_bits = int(match.group("num_bits"))
  base = match.group("base")
  value = match.group("value")

  if base == "b":
    value_int = int(value, 2)
  else :
    value_int = int(value, 16)

  py_bin_str = f"{value_int:0>{num_bits}b}"
  return py_bin_str

# Converts numbers from the following "verilog" form:
#
#   64'h[0-9a-fA-F]{16}
#   64'b[0-9a-fA-F]{64}
#
# into a python hex string:
#
#   [0-9a-fA-F]{16}
def verilog_num_to_hex(vnum: str) -> str:
  vbin = verilog_num_to_bin(vnum)
  lbin = len(vbin)
  assert (lbin % 4) == 0, f"Error: Bitwidth is not a multiple of 4. Cannot create hex value."

  lhex = lbin // 4
  py_hex_str = f"{int(vbin, 2):0>{lhex}x}"
  return py_hex_str

# Converts numbers from the following "verilog" form:
#
#   64'h[0-9a-fA-F]{16}
#   64'b[0-9a-fA-F]{64}
#
# into a python int.
def verilog_num_to_int(vnum: str) -> int:
  vbin = verilog_num_to_bin(vnum)
  return int(vbin, 2)

# Writes a bit in a numpy array.
def np_write_bit(
  words: np.ndarray,
  bit_ofst: int,
  value: int
) -> None:
  assert is_binary_int(value), f"Error: Expected 0/1 (received {value})"
  num_bits_word = words.itemsize * 8
  word_idx = bit_ofst // num_bits_word
  word_ofst = bit_ofst % num_bits_word

  word_orig = words[word_idx]
  if value == 0:
    word_new = clear_bit(word_orig, word_ofst)
  else:
    word_new = set_bit(word_orig, word_ofst)

  words[word_idx] = word_new

# Reads a bit in a numpy array.
def np_read_bit(
  words: np.ndarray,
  bit_ofst: int
) -> int:
  num_bits_word = words.itemsize * 8
  word_idx = bit_ofst // num_bits_word
  word_ofst = bit_ofst % num_bits_word
  bit = bits(words[word_idx], word_ofst, word_ofst)
  return bit

def set_bit(value, bit):
  return value | (1 << bit)

def clear_bit(value, bit):
  return value & ~(1 << bit)
