# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
from pathlib import Path

import numpy as np

import frame as fr
from bitstream import Bitstream
from frame import FrameAddressRegister


# Diffs 2 bitstreams.
#
# This function expects only a single bit to "logically" differ between the 2 bitstreams.
# This is for example a single bit in a LUT equation, or a single FDRE init value.
#
# In reality multiple "physical" bits will be modified as a result of the single
# logical bit being different. The reason is that some auxiliary control bits will
# also be configured depending on the LUT equation used.
def locate_config_difference(
  baseline_path: Path,
  modified_path: Path
) -> tuple[
  int, # IDCODE
  list[FrameAddressRegister], # FARs (multiple bits can change, hence why we use a list)
  list[str] # frame_ofsts (multiple bits can change, hence why we use a list). We use a string so we can encode whether
            # the bit at the given ofst is active-high or active-low based what we see change in the bitstreams.
]:
  # # Debug
  # print(f"{baseline_path.name} vs {modified_path.name}")

  # List of elements that differed between the bitstreams.
  diff_idcodes: list[int] = list()
  diff_fars: list[FrameAddressRegister] = list()
  diff_frameOfsts: list[str] = list()

  baseline_bitstream = Bitstream.from_file_path(baseline_path)
  modified_bitstream = Bitstream.from_file_path(modified_path)

  assert baseline_bitstream.header.fpga_part == modified_bitstream.header.fpga_part, f"Error: Comparing different parts {baseline_bitstream.header.fpga_part} and {modified_bitstream.header.fpga_part}"

  baseline_valid = (not baseline_bitstream.is_partial()) and (not baseline_bitstream.is_compressed())
  modified_valid = (not modified_bitstream.is_partial()) and (not modified_bitstream.is_compressed())
  assert baseline_valid, f"Error: {baseline_path} must be a full uncompressed bitstream!"
  assert modified_valid, f"Error: {modified_path} must be a full uncompressed bitstream!"

  baseline = baseline_bitstream.get_per_far_configuration_arrays()
  modified = modified_bitstream.get_per_far_configuration_arrays()

  # Sanity check that the bistreams have the same IDCODEs.
  baseline_idcodes = baseline.keys()
  modified_idcodes = modified.keys()
  assert baseline_idcodes == modified_idcodes, f"Error: Unequal IDCODEs detected"

  for idcode in baseline_idcodes:
    # Sanity check that the bitstreams have the same FARs.
    baseline_fars = baseline[idcode].keys()
    modified_fars = modified[idcode].keys()
    assert baseline_fars == modified_fars, f"Error: Unequal FARs detected"

    for far in baseline_fars:
      # Sanity check that the FAR is written the same number of times.
      baseline_frames = baseline[idcode][far]
      modified_frames = modified[idcode][far]
      assert len(baseline_frames) == len(modified_frames), f"Error: FARs written unequal number of times"

      for (baseline_frame, modified_frame) in zip(baseline_frames, modified_frames):
        # Sanity check that we are comparing the same offset in the bitstream.
        baseline_byteOfst = baseline_frame.byte_ofst
        modified_byteOfst = modified_frame.byte_ofst
        assert baseline_byteOfst == modified_byteOfst, f"Error: Comparing frames at different byte offsets {baseline_byteOfst} and {modified_byteOfst}"

        if not np.array_equal(baseline_frame.words, modified_frame.words):
          frame_ofsts = fr.diff_frame(baseline_frame, modified_frame)

          for frame_ofst in frame_ofsts:
            baseline_bit_value = baseline_frame.bit(frame_ofst)
            modified_bit_value = modified_frame.bit(frame_ofst)

            assert baseline_bit_value != modified_bit_value, f"Error: Expected bit values to differ!"
            if (baseline_bit_value == 0) and (modified_bit_value == 1):
              frame_ofst_str = f"{frame_ofst}"
            else:
              # The ! is to mark that the value is active-low.
              frame_ofst_str = f"!{frame_ofst}"

            diff_idcodes.append(idcode)
            diff_fars.append(far)
            diff_frameOfsts.append(frame_ofst_str)

            # Debug
            print(f"IDCODE = 0x{idcode:0>8x}, {far}, FRAME_OFST = {frame_ofst}, VALUE = {baseline_bit_value} | IDCODE = 0x{idcode:0>8x}, {far}, FRAME_OFST = {frame_ofst}, VALUE = {modified_bit_value}")
          print()

  # Sanity check that all IDCODEs are identical (they must be as otherwise changing something in
  # one column would cause a column in another SLR to change).
  assert len(set(diff_idcodes)) == 1, f"Error: Found multiple different bits in multiple IDCODEs!"

  return (diff_idcodes[0], diff_fars, diff_frameOfsts)

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Diffs two bitstreams.")
  parser.add_argument("bit_a", type=str, help="Input bitstream A (with header).")
  parser.add_argument("bit_b", type=str, help="Input bitstream B (with header).")
  args = parser.parse_args()

  locate_config_difference(Path(args.bit_a), Path(args.bit_b))

  print("Done")
