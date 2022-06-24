# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
import typing
from collections import defaultdict
from pathlib import Path

import more_itertools as miter
import pandas as pd

import format_json
import helpers
from arch_spec import ArchSpec
from frame import FrameAddressRegister
from frame_spec import FarBlockType


def extract_num_majors_and_minors(
  in_fars_csv_path: str | Path,
  idcodes_json_path: str | Path,
  fpga_part: str,
  out_json_path: str | Path
) -> None:
  # Create architecture spec as we need it to parse FARs.
  ar_spec = ArchSpec.create_spec(fpga_part)

  # Read input CSV file.
  df = pd.read_csv(in_fars_csv_path)
  idcodes_hex: list[str] = df["IDCODE"].tolist()
  fars_hex: list[str] = df["FAR"].tolist()

  # Read slrName-to-idcode mapping from input JSON file.
  slrName_to_idcodeHex: dict[str, str] = helpers.read_json(idcodes_json_path)

  # The CSV file contains IDCODEs and we want to reconstruct the SLR name, so we
  # invert the SLR name to IDCODE mapping (it is one-to-one, so it is safe to invert).
  idcodeHex_to_slrName = {v: k for (k, v) in slrName_to_idcodeHex.items()}

  slrName_fars: dict[str, list[FrameAddressRegister]] = defaultdict(list)
  for (idcodeHex, far_hex) in zip(idcodes_hex, fars_hex):
    slrName = idcodeHex_to_slrName[idcodeHex]
    far_int = int(far_hex, 16)
    far = FrameAddressRegister.from_int(far_int, ar_spec)
    slrName_fars[slrName].append(far)

  # Extract num majors and minors.
  increments = dump_fars_increments(slrName_fars)

  # Emit output file.
  with open(out_json_path, "w") as f:
    json_str = format_json.emit(increments, sort_keys=True)
    f.write(json_str)


def dump_fars_increments(
  slrName_fars: dict[str, list[FrameAddressRegister]]
) -> dict[str, typing.Any]:
  def get_row_dict(
    fars_in_row: list[FrameAddressRegister],
    key_prefix: str
  ) -> dict[str, typing.Any]:
    #   rows:
    #     0:
    #       num_{key_prefix}_colMajors: ...
    #       num_minors_per_{key_prefix}_colMajor: [...]
    #     1:
    #       num_{key_prefix}_colMajors: ...
    #       num_minors_per_{key_prefix}_colMajor: [...]
    #     ...

    # A COL boundary is encountered when the MINOR address cycles back to 0.
    per_col_fars = list(miter.split_when(
      fars_in_row,
      lambda a, b: (a.minor_addr != 0) and (b.minor_addr == 0)
    ))

    num_majors = len(per_col_fars)
    num_minors_per_major = [len(col_fars) for col_fars in per_col_fars]

    return {
      f"num_{key_prefix}_colMajors": num_majors,
      f"num_minors_per_{key_prefix}_colMajor": num_minors_per_major,
    }

  def get_slr_dict(
    fars_in_slr: list[FrameAddressRegister]
  ) -> dict[str, typing.Any]:
    std_fars_in_slr = [far for far in fars_in_slr if far.block_type == FarBlockType.CLB_IO_CLK]
    bram_fars_in_slr = [far for far in fars_in_slr if far.block_type == FarBlockType.BRAM_CONTENT]

    # A ROW boundary is encountered when the COL address cycles back to 0.
    per_row_std_fars = miter.split_when(
      std_fars_in_slr,
      lambda a, b: (a.col_addr != 0) and (b.col_addr == 0)
    )
    per_row_bram_fars = miter.split_when(
      bram_fars_in_slr,
      lambda a, b: (a.col_addr != 0) and (b.col_addr == 0)
    )

    rows_std_dict = {
      fars_in_row[0].row_addr: get_row_dict(fars_in_row, "std") for fars_in_row in per_row_std_fars
    }
    rows_bram_dict = {
      fars_in_row[0].row_addr: get_row_dict(fars_in_row, "bram") for fars_in_row in per_row_bram_fars
    }

    # Merge std/bram row-level dictionaries. It must be done manually as they
    # are nested dictionaries.
    rows_dict = dict()
    for row_addr in rows_std_dict:
      assert row_addr in rows_bram_dict, f"Error: Row {row_addr} is found in standard rows, but not in BRAM rows."
      row_std_dict = rows_std_dict[row_addr]
      row_bram_dict = rows_bram_dict[row_addr]
      rows_dict[row_addr] = {**row_std_dict, **row_bram_dict}

    slr_dict = {
      "rowMajors": rows_dict,
    }

    return slr_dict

  def get_slrs_dict(
    slrName_fars: dict[str, list[FrameAddressRegister]]
  ) -> dict[str, typing.Any]:
    slrs_dict = {
      slr_name: get_slr_dict(fars_in_slr) for (slr_name, fars_in_slr) in slrName_fars.items()
    }

    return slrs_dict

  return {"slrs": get_slrs_dict(slrName_fars)}

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Extracts all major row/col addresses and minor addresses.")
  parser.add_argument("in_fars_csv", type=str, help="Input CSV file containing all FARs.")
  parser.add_argument("idcodes_json", type=str, help="Input JSON file mapping the device's SLRs to their IDCODEs.")
  parser.add_argument("fpga_part", type=str, help="FPGA part number.")
  parser.add_argument("out_json", type=str, help="Output JSON file containing major row/col and minor addresses.")
  args = parser.parse_args()

  extract_num_majors_and_minors(args.in_fars_csv, args.idcodes_json, args.fpga_part, args.out_json)

  print("Done")
