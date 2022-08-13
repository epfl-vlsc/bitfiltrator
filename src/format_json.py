# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
import collections.abc as cabc
import json
import re
import sys
import typing

# DO NOT USE NON-STANDARD LIBRARIES IN THIS FILE!
# This program is called from TCL scripts inside vivado and vivado has a custom
# version of python3 embedded within it. Using custom libraries will result in
# an error being generated.

# Used to perform a rudimentary version of "natural" sorting so strings that contain
# numbers can be compared correctly. This function takes an input string and converts
# it to a tuple of strings/numbers.
#
# Ex: "ab123cd" => ("ab", 123, "cd")
#                         ^^^
#                         a number, not a string.
def key_to_tup(k: str) -> typing.Tuple:
  # Returns an int if the string can be converted to an int, otherwise returns
  # the original string.
  def try_int(s: str) -> typing.Union[str, int]:
    try:
      res = int(s)
    except ValueError:
      res = s
    return res

  # Need to use a capture group to ensure the separator is not discarded by re.split().
  #
  # docs.python.org/library/re.html#re.split:
  #
  #   Split string by the occurrences of pattern.
  #   If capturing parentheses are used in pattern, then the text of all groups in the pattern
  #   are also returned as part of the resulting list.
  parts = re.split(r"(\d+)", k)
  parts = [try_int(part) for part in parts]
  return tuple(parts)

def indent(x: str, amount: int = 2) -> str:
  lines = x.splitlines()
  lines_indented = [" " * amount + line for line in lines]
  return "\n".join(lines_indented)

def is_dict(x: typing.Any) -> bool:
  return isinstance(x, dict)

def is_list(x: typing.Any) -> bool:
  return isinstance(x, list) or isinstance(x, tuple)

def is_str(x: typing.Any) -> bool:
  return isinstance(x, str)

def is_num(x: typing.Any) -> bool:
  return isinstance(x, int) or isinstance(x, float)

def emit_dict(
  d: typing.Dict[typing.Any, typing.Any],
  sort_keys: bool = False
) -> str:
  def is_nested(d: typing.Dict[typing.Any, typing.Any]) -> bool:
    for (k, v) in d.items():
      if isinstance(v, cabc.Collection) and not isinstance(v, str):
        return True
    return False

  nested = is_nested(d)

  if sort_keys:
    # Important to use "natural" sorting as keys are strings, so we transform the
    # dict key to a tuple of strings/numbers and do a tuple-level comparison.
    # Note that the dict key can be of any type, but we must convert it to a string
    # before we can emit a JSON representation for it as JSON expects all keys
    # to be strings.
    d_ord = sorted(d.items(), key=lambda kv: key_to_tup(str(kv[0])))
  else:
    d_ord = d.items()

  content_lines: typing.List[str] = list()
  for (k, v) in d_ord:
    sub_str = f"\"{k}\": {emit(v, sort_keys)}"
    if nested:
      content_lines.append(indent(sub_str))
    else:
      content_lines.append(sub_str)

  if nested:
    content_str = ",\n".join(content_lines)
    d_str = f"{{\n{content_str}\n}}"
  else:
    content_str = ",".join(content_lines)
    d_str = f"{{{content_str}}}"

  return d_str

def emit_list(
  l: typing.List[typing.Any],
  sort_keys: bool = False
) -> str:
  def is_nested(l: typing.List[typing.Any]) -> bool:
    for v in l:
      if isinstance(v, cabc.Collection) and not isinstance(v, str):
        return True
    return False

  nested = is_nested(l)

  content_lines: typing.List[str] = list()
  for v in l:
    sub_str = emit(v, sort_keys)
    if nested:
      content_lines.append(indent(sub_str))
    else:
      content_lines.append(sub_str)

  if nested:
    # Nested arrays are emitted over multiple lines.
    content_str = ",\n".join(content_lines)
    l_str = f"[\n{content_str}\n]"
  else:
    # Leaf arrays are emitted over a single line.
    content_str = ",".join(content_lines)
    l_str = f"[{content_str}]"

  return l_str

def emit_str(
  s: str
) -> str:
  # JSON requires quotes around strings.
  return f"\"{s}\""

def emit_num(
  n: typing.Union[int, float]
) -> str:
  return f"{n}"

def emit(
  x: typing.Any,
  sort_keys: bool = False
) -> str:
  if is_dict(x):
    res = emit_dict(x, sort_keys)
  elif is_list(x):
    res = emit_list(x, sort_keys)
  elif is_str(x):
    res = emit_str(x)
  elif is_num(x):
    res = emit_num(x)
  else:
    assert False, f"Error: Cannot serialize unsupported type \"{type(x)}\" for object {x}."

  return res

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Formats JSON files. Keeps leaf-level arrays on a single line.")
  parser.add_argument("--sort_keys", action="store_true", help="Sorts objects by key.")
  parser.add_argument("f_in", type=str, nargs="?", help="Input JSON file. If not provided, the input is read from stdin.")
  parser.add_argument("f_out", type=str, nargs="?", help="Output JSON file. If not provided, the formatted output is written to stdout.")
  args = parser.parse_args()

  if args.f_in:
    with open(args.f_in, "r") as f:
      input_str = f.read()
  else:
    input_str = sys.stdin.read()

  output_str = emit(json.loads(input_str), args.sort_keys)

  if args.f_out:
    with open(args.f_out, "w") as f:
      f.write(output_str)
  else:
    print(output_str)
