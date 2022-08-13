# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
import re
import typing
from collections import defaultdict
from pathlib import Path

import format_json
import logic_location as ll
from arch_spec import ArchSpec
from frame import FrameAddressRegister


def extract_col_majors_from_ll(
  fpga_part: str,
  ll_path: str | Path,
  filter_regex: str,
  out_path: str | Path
) -> None:
  # Create architecture spec as we need it to parse FARs.
  ar_spec = ArchSpec.create_spec(fpga_part)

  # Extract major column addresses.
  logic_locs = ll.LogicLocationFile(ll_path)
  majors = get_majors(logic_locs, ar_spec, filter_regex)

  with open(out_path, "w") as f:
    json_str = format_json.emit(majors, sort_keys=True)
    f.write(json_str)

def get_majors(
  logic_locs: ll.LogicLocationFile,
  ar_spec: ArchSpec,
  filter_regex: str
) -> dict[str, typing.Any]:
  # We first split the logic locations by their type as we will put each type under
  # a different key in the final dict.
  bitLocType_bitLoc_dict: dict[str, list[ll.BitLoc]] = defaultdict(list)
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
  #     "slrs": {
  #       "SLR0": {
  #         "BramMemLoc": {
  #           "rowMajors": {
  #             "0": {
  #               "colMajors": {
  #                 "0": 0, // The key and value are the same for BRAMs, but for CLBs they will differ.
  #                 "1": 1,
  #                 ...
  #               }
  #             },
  #             "1": {
  #               "colMajors": {
  #                 "0": 0, // The key and value are the same for BRAMs, but for CLBs they will differ.
  #                 "1": 1,
  #                 ...
  #               }
  #             },
  #             ...
  #           }
  #         },
  #         "BramMemParityLoc": {
  #           "rowMajors": {
  #             "0": {
  #               "colMajors": {
  #                 "0": 0, // The key and value are the same for BRAMs, but for CLBs they will differ.
  #                 "1": 1,
  #                 ...
  #               }
  #             },
  #             "1": {
  #               "colMajors": {
  #                 "0": 0, // The key and value are the same for BRAMs, but for CLBs they will differ.
  #                 "1": 1,
  #                 ...
  #               }
  #             },
  #             ...
  #           }
  #         },
  #         "BramRegLoc": {
  #           "rowMajors": {
  #             "0": {
  #               "colMajors": {
  #                 "0": 9,
  #                 "1": 71,
  #                 "2": 80,
  #                 "3": 98,
  #                 ...
  #               }
  #             },
  #             "1": {
  #               "colMajors": {
  #                 "0": 9,
  #                 "1": 71,
  #                 "2": 80,
  #                 "3": 98,
  #                 ...
  #               }
  #             },
  #             ...
  #           }
  #         }
  #       }
  #     }
  #   }

  res = defaultdict(
    lambda: defaultdict(
      lambda: defaultdict(
        lambda: defaultdict(
          lambda: defaultdict(
            # We use a set as many entries in the logic location file may share the same column (BRAMs for example), and
            # we are only interested in which column numbers are used, not whether they are used multiple times or not.
            lambda: defaultdict(set)
          )
        )
      )
    )
  )
  for (bitLocType, bitLocList) in bitLocType_bitLoc_dict.items():
    for bitLoc in bitLocList:
      far = FrameAddressRegister.from_int(bitLoc.frame_addr, ar_spec)
      res["slrs"][bitLoc.slr_name][bitLocType]["rowMajors"][far.row_addr]["colMajors"].add((bitLoc.block_x, far.col_addr))

  # Sort the major columns list so it is easier to read.
  for (slrsKey, slrIdx_dict) in res.items():
    for (slrIdx, bitLocType_dict) in slrIdx_dict.items():
      for (bitLocType, rowsKey_dict) in bitLocType_dict.items():
        for (rowsKey, majorRows_dict) in rowsKey_dict.items():
          for (majorRow, colsKey_dict) in majorRows_dict.items():
            for (colsKey, majorCols_set) in colsKey_dict.items():
              majorCols_dict = { block_x: col_addr for (block_x, col_addr) in majorCols_set}
              res[slrsKey][slrIdx][bitLocType][rowsKey][majorRow][colsKey] = majorCols_dict

  return res

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Extracts all major column addresses from a logic-location file.")
  parser.add_argument("ll", type=str, help="Input logic-location file.")
  parser.add_argument("fpga_part", type=str, help="FPGA part number.")
  parser.add_argument("out_json", type=str, help="Output JSON file containing major col addresses.")
  parser.add_argument("--filter_regex", type=str, default=".*", help="Regular expression for name of logic location classes to keep in the output file.")
  args = parser.parse_args()

  extract_col_majors_from_ll(args.fpga_part, args.ll_path, args.filter_regex, args.out_json)

  print("Done")
