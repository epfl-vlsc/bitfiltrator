# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
import math
import re
from pathlib import Path

import joblib
import more_itertools as miter
import numpy as np

import frame as fr
import helpers
import resources
from arch_spec import ArchSpec
from bitstream import Bitstream
from frame import FrameAddressRegister


def lut_init_sweep_to_logic_loc(
  baseline_bitstream: str | Path,
  bitstream_dir: str | Path,
  out_ll: str | Path,
  filter_regex: str = ".*",
  process_cnt: int = 1,
):
  baseline_bit_path = Path(baseline_bitstream)
  baseline_bit = Bitstream.from_file_path(baseline_bit_path)

  input_bit_paths = [
    p
    for p in Path(bitstream_dir).glob(f"**/*")
    if re.search(filter_regex, str(p)) is not None
  ]

  lut_encodings = extract_lut_encoding(baseline_bit_path, input_bit_paths, process_cnt)
  dump_logic_loc(lut_encodings, baseline_bit.header.fpga_part, out_ll)

def is_power_of_two(n: int):
  return (n != 0) and (n & (n-1) == 0)

def is_one_hot_equation(equation: str) -> bool:
  equation_int = int(equation, 2)
  return is_power_of_two(equation_int)

def extract_filename_fields(p: Path) -> tuple[int, str]:
  pattern = r"lut_gen\[(?P<lut_idx>\d+)\]\.lut6_inst_b(?P<lut_equation>[01]{64}).bit.*"
  match = helpers.regex_match(pattern, p.name)
  lut_idx = int(match.group("lut_idx"))
  lut_equation = match.group("lut_equation")
  return (lut_idx, lut_equation)

def extract_lut_idx_from_filename(p: Path) -> int:
  (lut_idx, _) = extract_filename_fields(p)
  return lut_idx

def extract_lut_equation_from_filename(p: Path) -> str:
  (_, lut_equation) = extract_filename_fields(p)
  return lut_equation

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
        assert baseline_byteOfst == modified_byteOfst, f"Error: Comparing frames at different byte offsets"

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

            # # Debug
            # print(f"IDCODE = 0x{idcode:0>8x}, {far}, FRAME_OFST = {frame_ofst_str}")


  # Sanity check that all IDCODEs are identical (they must be as otherwise changing something in
  # one column would cause a column in another SLR to change).
  assert len(set(diff_idcodes)) == 1, f"Error: Found multiple different bits in multiple IDCODEs!"

  return (diff_idcodes[0], diff_fars, diff_frameOfsts)

def extract_lut_encoding(
  baseline_bit_path: Path,
  input_bit_paths: list[Path],
  process_cnt: int
) -> list[tuple[
  int, # lut idx
  int, # lut equation idx
  int, # IDCODE
  list[FrameAddressRegister], # FARs (multiple bits can change, hence why we return a list)
  list[str], # frame_ofsts (multiple bits can change, hence why we return a list). The str encodes the bit number and it's active-high/active-low status.
]]:
  # Use the lut idx in the file name to bucketize all paths.
  #   lut_idx -> iterable[Path]
  split_by_lut = miter.bucket(input_bit_paths, key=extract_lut_idx_from_filename)

  # LUTs are indexed as follows:
  #
  #   SLICE_X<x>Y<y_ofst>
  #     y_ofst =  0 -> lut_idx =   0 ..   7 (A6LUT .. H6LUT)
  #     y_ofst =  1 -> lut_idx =   8 ..  15 (A6LUT .. H6LUT)
  #     ...
  #     y_ofst = 59 -> lut_idx = 472 .. 479 (A6LUT .. H6LUT)

  # We prepare a set of batch arguments that we can then feed to a function
  # through joblib so we can parallelize encoding extraction.
  batch_args = list()
  for lut_idx in sorted(split_by_lut):
    modified_bit_paths = sorted(split_by_lut[lut_idx])
    for modified_bit_path in modified_bit_paths:
      lut_equation = extract_lut_equation_from_filename(modified_bit_path)
      assert is_one_hot_equation(lut_equation), f"Error: equation \"{lut_equation}\" is not a one-hot equation!"
      lut_equation_bit_idx = int(math.log2(int(lut_equation, 2)))

      batch_args.append((
        lut_idx,
        lut_equation_bit_idx,
        baseline_bit_path,
        modified_bit_path
      ))

  # # Debug
  # print(batch_args)

  idcode_fars_frameOfsts_list = joblib.Parallel(
    n_jobs=process_cnt,
    verbose=10
  )(
    joblib.delayed(
      locate_config_difference
    )(
      baseline_path, modified_path
    ) for (_, _, baseline_path, modified_path) in batch_args
  )

  # Sanity check that all IDCODEs are the same.

  lutIdx_lutEqIdx_idcode_fars_frameOfsts_list = [
    (lut_idx, lut_equation_idx, idcode, fars, frame_ofsts)
    for ((lut_idx, lut_equation_idx, _, _), (idcode, fars, frame_ofsts))
    in zip(batch_args, idcode_fars_frameOfsts_list)
  ]

  return lutIdx_lutEqIdx_idcode_fars_frameOfsts_list

def dump_logic_loc(
  lutIdx_lutEqIdx_idcode_far_frameOfst_list: list[tuple[
    int, # lut idx
    int, # lut equation idx
    int, # IDCODE
    list[FrameAddressRegister], # FARs (multiple bits can change, hence why we use a list)
    list[str], # frame_ofsts (multiple bits can change, hence why we return a list). The str encodes the bit number and it's active-high/active-low status.
  ]],
  fpga_part: str,
  out_file: str
) -> None:
  # Recall that we encoded LUT names as follows in this program:
  #
  #   SLICE_X<x>Y<y_ofst>
  #     y_ofst =  0 -> lut_idx =   0 ..   7 (A6LUT .. H6LUT)
  #     y_ofst =  1 -> lut_idx =   8 ..  15 (A6LUT .. H6LUT)
  #     ...
  #     y_ofst = 59 -> lut_idx = 472 .. 479 (A6LUT .. H6LUT)

  lutIdx_to_name = {
    idx: chr(ord("A") + idx)
    for idx in range(0, 8)
  }

  dev_summary = resources.get_device_summary(fpga_part)
  ar_spec = ArchSpec.create_spec(fpga_part)

  lines: list[str] = list()
  for (lut_idx, lut_equation_idx, idcode, fars, frame_ofsts) in lutIdx_lutEqIdx_idcode_far_frameOfst_list:
    # We use -1 as the bit offset so it is immediately obvious this is not an
    # official file generated by vivado, but a placeholder with similar structure.
    bit_ofst = -1
    slr_name = dev_summary.get_slr_name(idcode)
    slr_idx = dev_summary.get_slr_idx(slr_name)
    # We use any number for the X offset as it doesn't matter. We just need the
    # format to be valid, so I use 0.
    x_ofst = 0
    y_ofst = lut_idx // ar_spec.num_lut_per_clb()
    # I use a custom "Lut" type here to differentiate it from a LUTRAM/LUTROM.
    # This is just for internal parsing purposes later as I want to differentiate
    # between a LutramLoc and a LutLoc. A LutramLoc has the mem_type field set to
    # (Rom|Ram) whereas a LutLoc has the field set to Lut.
    mem_type = "Lut"
    lut_ofst_in_clb = lut_idx % ar_spec.num_lut_per_clb()
    mem_id = lutIdx_to_name[lut_ofst_in_clb]
    mem_bit = lut_equation_idx

    # Note that we have just changed 1 bit in a LUT's equation, but multiple bits change
    # in the underlying bitstream (see below for an example).
    #
    #   lut_gen[0].lut6_inst_b0000000000000000000000000000000000000000000000000000000000000001.bit.gz
    #   BLOCK_TYPE = CLB_IO_CLK, ROW_ADDR = 0, COL_ADDR = 167, MINOR_ADDR = 0, FRAME_OFST = 15
    #   BLOCK_TYPE = CLB_IO_CLK, ROW_ADDR = 0, COL_ADDR = 167, MINOR_ADDR = 0, FRAME_OFST = 1923
    #   BLOCK_TYPE = CLB_IO_CLK, ROW_ADDR = 0, COL_ADDR = 167, MINOR_ADDR = 0, FRAME_OFST = 1927
    #   BLOCK_TYPE = CLB_IO_CLK, ROW_ADDR = 0, COL_ADDR = 167, MINOR_ADDR = 0, FRAME_OFST = 1935
    #   BLOCK_TYPE = CLB_IO_CLK, ROW_ADDR = 0, COL_ADDR = 167, MINOR_ADDR = 0, FRAME_OFST = 1943
    #   BLOCK_TYPE = CLB_IO_CLK, ROW_ADDR = 0, COL_ADDR = 167, MINOR_ADDR = 0, FRAME_OFST = 1963
    #
    # The equation bit is the "outlier" (15 above). The other 5 bits are auxiliary control bits.
    #
    # To find the outlier we are interested in, we compute the median and select the
    # element furthest from it.

    # We transform the frame offsets to a numpy array so we can use its median computation code.
    frame_ofsts = np.array(frame_ofsts, dtype=np.uint32)
    median = np.median(frame_ofsts)
    delta_to_median = np.abs(frame_ofsts - median)
    largest_delta_idx = np.argmax(delta_to_median)

    equation_far: FrameAddressRegister = None
    equation_frame_ofst: int = None
    auxiliary_fars: list[FrameAddressRegister] = list()
    auxiliary_frame_ofsts: list[int] = list()
    for lidx in range(len(fars)):
      if lidx == largest_delta_idx:
        equation_far = fars[lidx]
        equation_frame_ofst = frame_ofsts[lidx]
      else:
        auxiliary_fars.append(fars[lidx])
        auxiliary_frame_ofsts.append(frame_ofsts[lidx])

    auxiliary_fars_str = ":".join([f"0x{far.to_hex()}" for far in auxiliary_fars])
    auxiliary_frame_ofsts_str = ":".join([f"{aux_frame_ofst}" for aux_frame_ofst in auxiliary_frame_ofsts])
    lines.append(f"Bit {bit_ofst} 0x{equation_far.to_hex()} {equation_frame_ofst} {slr_name} {slr_idx} Block=SLICE_X{x_ofst}Y{y_ofst} {mem_type}={mem_id}:{mem_bit} AuxiliaryFars={auxiliary_fars_str} AuxiliaryFrameOfsts={auxiliary_frame_ofsts_str}")

  with open(out_file, "w") as f_out:
    f_out.write("\n".join(lines))

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Reconstructs a logic location file from a set of bitstreams.")
  parser.add_argument("baseline_bitstream", type=str, help="Input baseline bitstream (without LUT equation sweep).")
  parser.add_argument("bitstream_dir", type=str, help="Input directory with bitstreams to parse for LUT encoding extraction.")
  parser.add_argument("out_ll", type=str, help="Output logic-location file containing.")
  parser.add_argument("--filter_regex", type=str, default=".*", help="Regular expression for name of files to read from bitstream directory.")
  parser.add_argument("--process_cnt", type=int, default=1, help="Joblib parallelism (use -1 to use all cores).")
  args = parser.parse_args()

  lut_init_sweep_to_logic_loc(
    args.baseline_bitstream,
    args.bitstream_dir,
    args.out_ll,
    args.filter_regex,
    args.process_cnt
  )