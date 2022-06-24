# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
import re
import typing
from collections import defaultdict
from pathlib import Path

import format_json
from arch_spec import ArchSpec
from frame import FrameAddressRegister
from logic_location import (BitLoc, BramLoc, BramMemLoc, BramMemParityLoc,
                            BramRegLoc, LogicLocationFile, LutramLoc, RegLoc)


def extract_encoding_from_logic_loc(
  ll: str | Path,
  fpga_part: str,
  out_json: str | Path,
  filter_regex: str = ".*"
) -> None:
  # Create architecture spec as we need it to parse FARs.
  ar_spec = ArchSpec.create_spec(fpga_part)

  # Extract major column addresses.
  logic_locs = LogicLocationFile(ll)
  encoding = get_encoding(logic_locs, ar_spec, filter_regex)

  with open(out_json, "w") as f:
    json_str = format_json.emit(encoding, sort_keys=True)
    f.write(json_str)

# Sanity check. All SLR numbers and major row/col addresses should be constant
# as we are only examining a single column.
def fars_are_valid_for_encoding_extraction(
  bit_locs: list[BitLoc],
  ar_spec: ArchSpec
) -> bool:
  # References
  ref_bit_loc = bit_locs[0]
  ref_far = FrameAddressRegister.from_int(ref_bit_loc.frame_addr, ar_spec)

  for bit_loc in bit_locs:
    far = FrameAddressRegister.from_int(bit_loc.frame_addr, ar_spec)

    # Just the minor address can differ!
    slr_valid = bit_loc.slr_number == ref_bit_loc.slr_number
    reserved_valid = far.reserved == ref_far.reserved
    block_type_valid = far.block_type == ref_far.block_type
    row_addr_valid = far.row_addr == ref_far.row_addr
    col_addr_valid = far.col_addr == ref_far.col_addr

    valid = all([slr_valid, reserved_valid, block_type_valid, row_addr_valid, col_addr_valid])
    if not valid:
      return False

  return True

def bram_blocks_valid_for_encoding_extraction(
  bit_locs: list[BramLoc]
) -> bool:
  ref_bit_loc = bit_locs[0]

  for bit_loc in bit_locs:
    valid = (bit_loc.bram_mem_size_kb == ref_bit_loc.bram_mem_size_kb) and (bit_loc.bram_parity_size_kb == ref_bit_loc.bram_parity_size_kb)
    if not valid:
      return False

  return True

# Find min Y index as we need to offset our numbers by this minimal value when storing the column's encoding.
def find_base_Y(
  bit_locs: list[BitLoc]
):
  ys: set[int] = set()
  for bit_loc in bit_locs:
    ys.add(bit_loc.block_y)
  return min(ys)

def get_BramMemLoc_encoding(
  bit_locs: list[BramMemLoc],
  ar_spec: ArchSpec
) -> dict[str, typing.Any]:
  # We want the resulting dictionary to look like this:
  #
  #   "Y_ofst": {
  #     "0": {
  #       "minor": [ ... ],     // 32K bits (1 bit per BRAM data bit).
  #       "frame_ofst": [ ... ] // 32K bits (1 bit per BRAM data bit).
  #     },
  #     "1": {
  #       "minor": [ ... ],
  #       "frame_ofst": [ ... ]
  #     },
  #     ...
  #   }

  bram_blocks_valid_for_encoding_extraction(bit_locs)
  y_min = find_base_Y(bit_locs)

  # We first create a "tmp" dict that maps every BRAM's bit to its minor and frame offset.
  #
  #   "Y_ofst": {
  #     "0": {
  #       "minor": {
  #         "0": <single_num>,
  #         "1": <single_num>,
  #         ...
  #       },
  #       "frame_ofst": {
  #         "0": <single_num>,
  #         "1": <single_num>,
  #         ...
  #       }
  #     },
  #     ...
  #   }

  tmp = defaultdict(
    lambda: defaultdict(
      lambda: defaultdict(
        # This is a 4th level that will not exist in the final result. It maps a bit ofst within
        # the BRAM memory region to a int (minor/frame_ofst).
        lambda: defaultdict(int)
      )
    )
  )

  for bit_loc in bit_locs:
    far = FrameAddressRegister.from_int(bit_loc.frame_addr, ar_spec)
    y = bit_loc.block_y - y_min
    memBit = bit_loc.mem_bit
    minor = far.minor_addr
    frame_ofst = bit_loc.frame_ofst
    tmp["Y_ofst"][y]["minor"][memBit] = minor
    tmp["Y_ofst"][y]["frame_ofst"][memBit] = frame_ofst

  # Sanity check that all memory bits of the BRAM are present in the tmp dict. We already
  # know that all bram blocks are of the same size as we checked earlier. Now we just need
  # to know what the size is so we can check if all bits are present.
  bram_mem_size_bits = bit_locs[0].bram_mem_size_kb * 1024
  for (yOfstKey, yIdx_dict) in tmp.items():
    for (yIdx, minorOrFrameOfst_dict) in yIdx_dict.items():
      for (minorOrFrameOfstKey, memBit_dict) in minorOrFrameOfst_dict.items():
        bit_indices = set(memBit_dict.keys())
        expected_indices = set(range(0, bram_mem_size_bits))
        bit_indices_missing = expected_indices.difference(bit_indices)
        assert len(bit_indices_missing) == 0, f"Error: Expected to find encoding of all bits (0-{bram_mem_size_bits-1}), but BRAM at Y ofst {yIdx} is missing definitions for bits {sorted(bit_indices_missing)}!"

  # Now that we have collected a dict-level view of a BRAM's bits, we transform it into an
  # array-level view since we are sure that the keys are 0-(bram_mem_size_bits-1). The key
  # is therefore redundant and we can use an implicit array index instead.

  res = defaultdict(
    lambda: defaultdict(
      lambda: defaultdict(list)
    )
  )

  for (yOfstKey, yIdx_dict) in tmp.items():
    for (yIdx, minorOrFrameOfst_dict) in yIdx_dict.items():
      for (minorOrFrameOfstKey, memBit_dict) in minorOrFrameOfst_dict.items():
        # The keys of the dict are the bit indices of the BRAM. We sort by the key
        # to ensure the BRAM is ordered correctly. We discard the bitIdx
        # as we are sure it goes from 0 to (bram_mem_size_bits-1) (we checked earlier).
        sorted_bit_encoding = [value for (bitIdx, value) in sorted(memBit_dict.items())]
        res[yOfstKey][yIdx][minorOrFrameOfstKey] = sorted_bit_encoding

  return res

def get_BramMemParityLoc_encoding(
  bit_locs: list[BramMemParityLoc],
  ar_spec: ArchSpec
) -> dict[str, typing.Any]:
  # We want the resulting dictionary to look like this:
  #
  #   "Y_ofst": {
  #     "0": {
  #       "minor": [ ... ],     // 2K bits (1 bit per BRAM parity bit).
  #       "frame_ofst": [ ... ] // 2K bits (1 bit per BRAM parity bit).
  #     },
  #     "1": {
  #       "minor": [ ... ],
  #       "frame_ofst": [ ... ]
  #     },
  #     ...
  #   }

  bram_blocks_valid_for_encoding_extraction(bit_locs)
  y_min = find_base_Y(bit_locs)

  # We first create a "tmp" dict that maps every BRAM's parity bit to its minor and frame offset.
  #
  #   "Y_ofst": {
  #     "0": {
  #       "minor": {
  #         "0": <single_num>,
  #         "1": <single_num>,
  #         ...
  #       },
  #       "frame_ofst": {
  #         "0": <single_num>,
  #         "1": <single_num>,
  #         ...
  #       }
  #     },
  #     ...
  #   }

  tmp = defaultdict(
    lambda: defaultdict(
      lambda: defaultdict(
        # This is a 4th level that will not exist in the final result. It maps a bit ofst within
        # the BRAM parity region to a int (minor/frame_ofst).
        lambda: defaultdict(int)
      )
    )
  )

  for bit_loc in bit_locs:
    far = FrameAddressRegister.from_int(bit_loc.frame_addr, ar_spec)
    y = bit_loc.block_y - y_min
    parBit = bit_loc.par_bit
    minor = far.minor_addr
    frame_ofst = bit_loc.frame_ofst
    tmp["Y_ofst"][y]["minor"][parBit] = minor
    tmp["Y_ofst"][y]["frame_ofst"][parBit] = frame_ofst

  # Sanity check that all parity bits of the BRAM are present in the tmp dict. We already
  # know that all bram blocks are of the same size as we checked earlier. Now we just need
  # to know what the size is so we can check if all bits are present.
  bram_parity_size_bits = bit_locs[0].bram_parity_size_kb * 1024
  for (yOfstKey, yIdx_dict) in tmp.items():
    for (yIdx, minorOrFrameOfst_dict) in yIdx_dict.items():
      for (minorOrFrameOfstKey, memBit_dict) in minorOrFrameOfst_dict.items():
        bit_indices = set(memBit_dict.keys())
        expected_indices = set(range(0, bram_parity_size_bits))
        bit_indices_missing = expected_indices.difference(bit_indices)
        assert len(bit_indices_missing) == 0, f"Error: Expected to find encoding of all bits (0-{bram_parity_size_bits-1}), but BRAM at Y ofst {yIdx} is missing definitions for bits {sorted(bit_indices_missing)}!"

  # Now that we have collected a dict-level view of a BRAM's bits, we transform it into an
  # array-level view since we are sure that the keys are 0-(bram_parity_size_bits-1). The key
  # is therefore redundant and we can use an implicit array index instead.

  res = defaultdict(
    lambda: defaultdict(
      lambda: defaultdict(list)
    )
  )

  for (yOfstKey, yIdx_dict) in tmp.items():
    for (yIdx, minorOrFrameOfst_dict) in yIdx_dict.items():
      for (minorOrFrameOfstKey, parBit_dict) in minorOrFrameOfst_dict.items():
        # The keys of the dict are the bit indices of the BRAM. We sort by the key
        # to ensure the BRAM is ordered correctly. We discard the bitIdx
        # as we are sure it goes from 0 to (bram_parity_size_bits-1) (we checked earlier).
        sorted_bit_encoding = [value for (bitIdx, value) in sorted(parBit_dict.items())]
        res[yOfstKey][yIdx][minorOrFrameOfstKey] = sorted_bit_encoding

  return res

def get_BramRegLoc_encoding(
  bit_locs: list[BramRegLoc],
  ar_spec: ArchSpec
) -> dict[str, typing.Any]:
  # We want the resulting dictionary to look like this:
  #
  #  "Y_ofst": {
  #    "0": {
  #      "minor": [ ... ],     // 64 bits (native data width of the BRAM).
  #      "frame_ofst": [ ... ] // 64 bits (native data width of the BRAM).
  #    },
  #    "1": {
  #      "minor": [ ... ],
  #      "frame_ofst": [ ... ]
  #    },
  #    ...
  #  }

  # TODO: skipping as we don't need a way to change the power-up value of these registers at the moment.
  return dict()

def get_LutramLoc_encoding(
  bit_locs: list[LutramLoc],
  ar_spec: ArchSpec
) -> dict[str, typing.Any]:
  # We want the resulting dictionary to look like this:
  #
  #   "Y_ofst": {
  #     "0": {
  #       "minor": {
  #         "A6LUT": [...], // 64 bits (1 bit per LUT config bit).
  #         "B6LUT": [...],
  #         ...
  #       },
  #       "frame_ofst": {
  #         "A6LUT": [...], // 64 bits (1 bit per LUT config bit).
  #         "B6LUT": [...],
  #         ...,
  #       }
  #     },
  #     "1": {
  #       "minor": {
  #         "A6LUT": [...], // 64 bits (1 bit per LUT config bit).
  #         "B6LUT": [...],
  #         ...
  #       },
  #       "frame_ofst": {
  #         "A6LUT": [...], // 64 bits (1 bit per LUT config bit).
  #         "B6LUT": [...],
  #         ...,
  #       }
  #     },
  #     ...
  #   }

  y_min = find_base_Y(bit_locs)

  # We first create a "tmp" dict that maps every lut's bit to its minor and frame offset.
  #
  #   "Y_ofst": {
  #     "0": {
  #       "minor": {
  #         "A": { // This letter is derived from the bit_loc's "mem_id" field. We will change it to "A6LUT" later.
  #           "0": <single_num>,
  #           "1": <single_num>,
  #           ...
  #         },
  #         ...
  #       },
  #       "frame_ofst": {
  #         "A": {
  #           "0": <single_num>,
  #           "1": <single_num>,
  #           ...
  #         },
  #         ...
  #       }
  #     },
  #     ...
  #   }

  tmp = defaultdict(
    lambda: defaultdict(
      lambda: defaultdict(
        lambda: defaultdict(
          # This is a 5th level that will not exist in the final result. It maps a bit ofst within
          # the LUT's equation to a int (minor/frame_ofst).
          lambda: defaultdict(int)
        )
      )
    )
  )

  for bit_loc in bit_locs:
    far = FrameAddressRegister.from_int(bit_loc.frame_addr, ar_spec)
    y = bit_loc.block_y - y_min
    lutName = bit_loc.mem_id
    lutBit = bit_loc.mem_bit
    minor = far.minor_addr
    frame_ofst = bit_loc.frame_ofst
    tmp["Y_ofst"][y]["minor"][lutName][lutBit] = minor
    tmp["Y_ofst"][y]["frame_ofst"][lutName][lutBit] = frame_ofst

  # Sanity check that all bits of the LUT are present in the tmp dict.
  for (yOfstKey, yIdx_dict) in tmp.items():
    for (yIdx, minorOrFrameOfst_dict) in yIdx_dict.items():
      for (minorOrFrameOfstKey, lutName_dict) in minorOrFrameOfst_dict.items():
        for (lutName, lutBit_dict) in lutName_dict.items():
          bit_indices = set(lutBit_dict.keys())
          expected_indices = set(range(0, 64))
          bit_indices_missing = expected_indices.difference(bit_indices)
          assert len(bit_indices_missing) == 0, f"Error: Expected to find encoding of all bits (0-63), but {lutName} at Y ofst {yIdx} is missing definitions for bits {sorted(bit_indices_missing)}!"

  # Now that we have collected a dict-level view of a LUT's bits, we transform it into an
  # array-level view since we are sure that the keys are 0-63 (we just checked). The key
  # is therefore redundant and we can use an implicit array index instead.

  res = defaultdict(
    lambda: defaultdict(
      lambda: defaultdict(
        lambda: defaultdict(list)
      )
    )
  )

  for (yOfstKey, yIdx_dict) in tmp.items():
    for (yIdx, minorOrFrameOfst_dict) in yIdx_dict.items():
      for (minorOrFrameOfstKey, lutName_dict) in minorOrFrameOfst_dict.items():
        for (lutName, lutBit_dict) in lutName_dict.items():
          # The keys of the dict are the bit indices of the LUT. We sort by the key
          # to ensure the LUT equation is ordered correctly. We discard the bitIdx
          # as we are sure it goes from 0 to 63 (we checked earlier).
          sorted_bit_encoding = [value for (bitIdx, value) in sorted(lutBit_dict.items())]
          # The lutName is simply "[ABCDEFGH]" in the logic location file, but I want
          # the same name as in Vivado "[ABCDEFGH]6LUT".
          lutName_final = f"{lutName}6LUT"
          res[yOfstKey][yIdx][minorOrFrameOfstKey][lutName_final] = sorted_bit_encoding

  return res

def get_RegLoc_encoding(
  bit_locs: list[RegLoc],
  ar_spec: ArchSpec
) -> dict[str, typing.Any]:
  # We want the resulting dictionary to look like this:
  #
  #   "Y_ofst": {
  #     "0": {
  #       "minor": {
  #         "AFF":  <single_num>, // 1 bit (each reg is 1 bit in the device).
  #         "AFF2": <single_num>,
  #         "BFF":  <single_num>,
  #         "BFF2": <single_num>,
  #         ...
  #       },
  #       "frame_ofst": {
  #         "AFF":  <single_num>, // 1 bit (each reg is 1 bit in the device).
  #         "AFF2": <single_num>,
  #         "BFF":  <single_num>,
  #         "BFF2": <single_num>,
  #         ...
  #       }
  #     },
  #     "1": {
  #       "minor": {
  #         "AFF":  <single_num>, // 1 bit (each reg is 1 bit in the device).
  #         "AFF2": <single_num>,
  #         "BFF":  <single_num>,
  #         "BFF2": <single_num>,
  #         ...
  #       },
  #       "frame_ofst": {
  #         "AFF":  <single_num>, // 1 bit (each reg is 1 bit in the device).
  #         "AFF2": <single_num>,
  #         "BFF":  <single_num>,
  #         "BFF2": <single_num>,
  #         ...
  #       }
  #     },
  #     ...
  #   }

  y_min = find_base_Y(bit_locs)

  res = defaultdict(
    lambda: defaultdict(
      lambda: defaultdict(
        lambda: defaultdict(int)
      )
    )
  )

  for bit_loc in bit_locs:
    far = FrameAddressRegister.from_int(bit_loc.frame_addr, ar_spec)
    y = bit_loc.block_y - y_min
    regName = bit_loc.reg
    minor = far.minor_addr
    frame_ofst = bit_loc.frame_ofst
    res["Y_ofst"][y]["minor"][regName] = minor
    res["Y_ofst"][y]["frame_ofst"][regName] = frame_ofst

  return res

def get_encoding(
  logic_locs: LogicLocationFile,
  ar_spec: ArchSpec,
  filter_regex: str
) -> dict[str, typing.Any]:
  # We first split the logic locations by their type as we will put each type under
  # a different key in the final dict.
  bitLocType_bitLoc_dict: dict[str, list[BitLoc]] = defaultdict(list)
  for bit_loc in logic_locs.bit_locs:
    bit_loc_class_name = bit_loc.__class__.__name__
    if re.match(filter_regex, bit_loc_class_name):
      bitLocType_bitLoc_dict[bit_loc_class_name].append(bit_loc)

  # Display number of entries per type.
  for (bitLocType, bit_locs) in bitLocType_bitLoc_dict.items():
    print(f"Num {bitLocType} = {len(bit_locs)}")

  # We want the resulting dictionary to look liks this:
  #
  #   {
  #     "BramMemLoc": {
  #       ...
  #     },
  #     "BramMemParityLoc": {
  #       ...
  #     },
  #     "BramRegLoc": {
  #       ...
  #     },
  #     "LutLoc": {
  #       ...
  #     },
  #     "RegLoc": {
  #       ...
  #     }
  #   }

  res = dict()
  for (bitLocType, bit_locs) in bitLocType_bitLoc_dict.items():
    assert fars_are_valid_for_encoding_extraction(bit_locs, ar_spec), f"Error: The SLR numbers and major row/col addresses are not constant for entries of type {bitLocType} in the logic-location file!"

    bit_loc = bit_locs[0]
    if bitLocType == "BramMemLoc":
      res[bitLocType] = get_BramMemLoc_encoding(bit_locs, ar_spec)
    elif bitLocType == "BramMemParityLoc":
      res[bitLocType] = get_BramMemParityLoc_encoding(bit_locs, ar_spec)
    elif bitLocType == "BramRegLoc":
      res[bitLocType] = get_BramRegLoc_encoding(bit_locs, ar_spec)
    elif (bitLocType == "LutramLoc") or (bitLocType == "LutLoc"):
      # NOTE: Should technically use bitLocType here, but I do not want to differentiate between LUTs and LUTRAMs in the
      # architecture summary files (the INIT bits we were interested in ended up having the same encoding for LUTRAMs
      # and standard LUTs when we extracted the data).
      res["LutLoc"] = get_LutramLoc_encoding(bit_locs, ar_spec)
    elif bitLocType == "RegLoc":
      res[bitLocType] = get_RegLoc_encoding(bit_locs, ar_spec)
    else:
      assert False, f"Error: Unknown type {bitLocType}"

  return res

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Extracts the encoding of a column from a logic-location file.")
  parser.add_argument("ll", type=str, help="Input logic-location file.")
  parser.add_argument("fpga_part", type=str, help="FPGA part number.")
  parser.add_argument("out_json", type=str, help="Output JSON file containing the column's encoding.")
  parser.add_argument("--filter_regex", type=str, default=".*", help="Regular expression for name of logic location classes to keep in the output file.")
  args = parser.parse_args()

  extract_encoding_from_logic_loc(args.ll, args.fpga_part, args.out_json, args.filter_regex)

  print("Done")
