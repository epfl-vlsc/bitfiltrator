# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
import re

import resources

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Compares BRAM minor/frame_ofsts with those of project U-Ray.")
  parser.add_argument("uray_bram_db", type=str, help="Input BRAM DB from project U-Ray.")
  args = parser.parse_args()

  fpga_part = "xcau25p-ffvb676-1-e"
  arch_summary = resources.get_arch_summary(fpga_part)

  (our_lower_mem_minors, our_lower_mem_frameOfsts) = arch_summary.get_bram_mem_loc(0)
  (our_upper_mem_minors, our_upper_mem_frameOfsts) = arch_summary.get_bram_mem_loc(1)
  (our_lower_parity_minors, our_lower_parity_frameOfsts) = arch_summary.get_bram_parity_loc(0)
  (our_upper_parity_minors, our_upper_parity_frameOfsts) = arch_summary.get_bram_parity_loc(1)

  their_lower_mem_minors = [0] * len(our_lower_mem_minors)
  their_lower_mem_frameOfsts = [0] * len(our_lower_mem_frameOfsts)
  their_lower_parity_minors = [0] * len(our_lower_parity_minors)
  their_lower_parity_frameOfsts = [0] * len(our_lower_parity_frameOfsts)

  their_upper_mem_minors = [0] * len(our_upper_mem_minors)
  their_upper_mem_frameOfsts = [0] * len(our_upper_mem_frameOfsts)
  their_upper_parity_minors = [0] * len(our_upper_parity_minors)
  their_upper_parity_frameofsts = [0] * len(our_upper_parity_frameOfsts)

  with open(args.uray_bram_db, "r") as f:
    lines = [l.strip() for l in f.readlines()]

    for line in lines:
      init_pattern = r"BRAM\.RAMB18E2_(?P<lower_upper>[LU])\.(?P<key>INITP?)_(?P<init_idx_hex>[0-9a-fA-F]{2})\[(?P<bit_idx_dec>\d+)\] (?P<minor>\d+)_(?P<frame_ofst>\d+)"
      init_match = re.search(init_pattern, line)
      if init_match:

        lower_upper = init_match.group("lower_upper")
        key = init_match.group("key")
        init_idx_hex = init_match.group("init_idx_hex")
        init_idx = int(init_idx_hex, 16)
        bit_idx = int(init_match.group("bit_idx_dec"))
        minor = int(init_match.group("minor"))
        frame_ofst = int(init_match.group("frame_ofst"))

        # print(f"init_idx = {init_idx}, bit_idx = {bit_idx}, minor = {minor}, frame_ofst = {frame_ofst}")

        is_lower = lower_upper == "L"
        is_mem = key == "INIT"

        abs_idx = init_idx * 256 + bit_idx

        if is_lower and is_mem:
          their_lower_mem_minors[abs_idx] = minor
          their_lower_mem_frameOfsts[abs_idx] = frame_ofst
        elif is_lower and not is_mem:
          their_lower_parity_minors[abs_idx] = minor
          their_lower_parity_frameOfsts[abs_idx] = frame_ofst
        elif not is_lower and is_mem:
          their_upper_mem_minors[abs_idx] = minor
          their_upper_mem_frameOfsts[abs_idx] = frame_ofst
        elif not is_lower and not is_mem:
          their_upper_parity_minors[abs_idx] = minor
          their_upper_parity_frameofsts[abs_idx] = frame_ofst

  assert our_lower_mem_minors == their_lower_mem_minors
  assert our_lower_mem_frameOfsts == their_lower_mem_frameOfsts
  assert our_lower_parity_minors == their_lower_parity_minors
  assert our_lower_parity_frameOfsts == their_lower_parity_frameOfsts

  assert our_upper_mem_minors == their_upper_mem_minors
  assert our_upper_mem_frameOfsts == their_upper_mem_frameOfsts
  assert our_upper_parity_minors == their_upper_parity_minors
  assert our_upper_parity_frameOfsts == their_upper_parity_frameofsts

  print(f"All OK")
