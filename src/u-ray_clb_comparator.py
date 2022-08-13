# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
import re
from collections import defaultdict

import resources


def parse_db(
  db_file: str
) -> list[str]:
  with open(db_file, "r") as f:
    lines = [l.strip() for l in f.readlines()]
    # We discard the leading tile type name prefix so we can compare many different tile types
    # using the same code later.

    new_lines = list()
    for l in lines:
      start_idx = l.find(".")
      # The +1 is to skip the "." itself.
      new_line = l[start_idx+1:]
      new_lines.append(new_line)

    return new_lines

def extract_lut_config(
  lines: list[str]
) -> tuple[
  dict[
    str, # resource (A6LUT, B6LUT, ...)
    list[int] # minors
  ],
  dict[
    str, # resource (A6LUT, B6LUT, ...)
    list[int] # frame_ofsts
  ]
]:
  minor_config = defaultdict(
    lambda: [0] * 64
  )
  frameOfst_config = defaultdict(
    lambda: [0] * 64
  )

  for line in lines:
    lut_pattern = r"(?P<letter>[ABCDEFGH])LUT\.INIT\[(?P<init_idx>\d+)\]\s+(?P<minor>\d+)_(?P<frame_ofst>\d+)"
    lut_match = re.search(lut_pattern, line)

    if lut_match:
      letter = lut_match.group("letter")
      init_idx = int(lut_match.group("init_idx"))
      minor = int(lut_match.group("minor"))
      frame_ofst = int(lut_match.group("frame_ofst"))

      key = f"{letter}6LUT"

      minor_config[key][init_idx] = minor
      frameOfst_config[key][init_idx] = frame_ofst

  return (minor_config, frameOfst_config)

def extract_reg_config(
  lines: list[str]
) -> tuple[
  dict[
    str, # resource (AFF, BFF, ...)
    list[int] # minors
  ],
  dict[
    str, # resource (AFF, BFF, ...)
    list[int] # frame_ofsts
  ]
]:
  minor_config = dict()
  frameOfst_config = dict()

  for line in lines:
    reg_pattern = r"(?P<letter>[ABCDEFGH])(?P<ff_type>FF2?)\.INIT\.V0\s+(?P<minor>\d+)_(?P<frame_ofst>\d+)"
    reg_match = re.search(reg_pattern, line)

    if reg_match:
      letter = reg_match.group("letter")
      ff_type = reg_match.group("ff_type")
      minor = int(reg_match.group("minor"))
      frame_ofst = int(reg_match.group("frame_ofst"))

      key = f"{letter}{ff_type}"

      minor_config[key] = minor
      frameOfst_config[key] = frame_ofst

  return (minor_config, frameOfst_config)

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Compares LUT/FF minor/frame_ofsts with those of project U-Ray.")
  parser.add_argument("uray_clel_l_db", type=str, help="Input CLEL_L DB from project U-Ray.")
  parser.add_argument("uray_clel_r_db", type=str, help="Input CLEL_R DB from project U-Ray.")
  parser.add_argument("uray_clem_db", type=str, help="Input CLEM DB from project U-Ray.")
  parser.add_argument("uray_clem_r_db", type=str, help="Input CLEM_R DB from project U-Ray.")
  args = parser.parse_args()

  fpga_part = "xcau25p-ffvb676-1-e"
  arch_summary = resources.get_arch_summary(fpga_part)

  clel_l_lines = parse_db(args.uray_clel_l_db)
  clel_r_lines = parse_db(args.uray_clel_r_db)
  clem_lines = parse_db(args.uray_clem_db)
  clem_r_lines = parse_db(args.uray_clem_r_db)

  (their_clel_l_lut_minors, their_clel_l_lut_frameOfsts) = extract_lut_config(clel_l_lines)
  (their_clel_r_lut_minors, their_clel_r_lut_frameOfsts) = extract_lut_config(clel_r_lines)
  (their_clem_lut_minors, their_clem_lut_frameOfsts) = extract_lut_config(clem_lines)
  (their_clem_r_lut_minors, their_clem_r_lut_frameOfsts) = extract_lut_config(clem_r_lines)

  (their_clel_l_reg_minors, their_clel_l_reg_frameOfsts) = extract_reg_config(clel_l_lines)
  (their_clel_r_reg_minors, their_clel_r_reg_frameOfsts) = extract_reg_config(clel_r_lines)
  (their_clem_reg_minors, their_clem_reg_frameOfsts) = extract_reg_config(clem_lines)
  (their_clem_r_reg_minors, their_clem_r_reg_frameOfsts) = extract_reg_config(clem_r_lines)

  # Check LUTs
  for letter in "ABCDEFGH":
    lut_key = f"{letter}6LUT"
    (our_clel_l_lut_minors, our_clel_l_lut_frameOfsts) = arch_summary.get_lut_loc("CLEL_L", 0, lut_key)
    (our_clel_r_lut_minors, our_clel_r_lut_frameOfsts) = arch_summary.get_lut_loc("CLEL_R", 0, lut_key)
    (our_clem_lut_minors, our_clem_lut_frameOfsts) = arch_summary.get_lut_loc("CLEM", 0, lut_key)
    (our_clem_r_lut_minors, our_clem_r_lut_frameOfsts) = arch_summary.get_lut_loc("CLEM_R", 0, lut_key)

    assert our_clel_l_lut_minors == their_clel_l_lut_minors[lut_key]
    assert our_clel_l_lut_frameOfsts == their_clel_l_lut_frameOfsts[lut_key]
    assert our_clel_r_lut_minors == their_clel_r_lut_minors[lut_key]
    assert our_clel_r_lut_frameOfsts == their_clel_r_lut_frameOfsts[lut_key]
    assert our_clem_lut_minors == their_clem_lut_minors[lut_key]
    assert our_clem_lut_frameOfsts == their_clem_lut_frameOfsts[lut_key]
    assert our_clem_r_lut_minors == their_clem_r_lut_minors[lut_key]
    assert our_clem_r_lut_frameOfsts == their_clem_r_lut_frameOfsts[lut_key]

  # Check regs
  for letter in "ABCDEFGH":
    for idx in ["", "2"]:
      reg_key = f"{letter}FF{idx}"
      (our_clel_l_reg_minors, our_clel_l_reg_frameOfsts) = arch_summary.get_reg_loc("CLEL_L", 0, reg_key)
      (our_clel_r_reg_minors, our_clel_r_reg_frameOfsts) = arch_summary.get_reg_loc("CLEL_R", 0, reg_key)
      (our_clem_reg_minors, our_clem_reg_frameOfsts) = arch_summary.get_reg_loc("CLEM", 0, reg_key)
      (our_clem_r_reg_minors, our_clem_r_reg_frameOfsts) = arch_summary.get_reg_loc("CLEM_R", 0, reg_key)

      assert our_clel_l_reg_minors == their_clel_l_reg_minors[reg_key]
      assert our_clel_l_reg_frameOfsts == their_clel_l_reg_frameOfsts[reg_key]
      assert our_clel_r_reg_minors == their_clel_r_reg_minors[reg_key]
      assert our_clel_r_reg_frameOfsts == their_clel_r_reg_frameOfsts[reg_key]
      assert our_clem_reg_minors == their_clem_reg_minors[reg_key]
      assert our_clem_reg_frameOfsts == their_clem_reg_frameOfsts[reg_key]
      assert our_clem_r_reg_minors == their_clem_r_reg_minors[reg_key]
      assert our_clem_r_reg_frameOfsts == their_clem_r_reg_frameOfsts[reg_key]


  print(f"All OK")
