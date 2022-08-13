# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
import typing
from collections import defaultdict
from pathlib import Path

import format_json
import helpers
import resources
from extract_all_frame_addresses import extract_all_frame_addresses
from extract_clb_col_tile_types import extract_clb_col_tile_types
from extract_col_majors_from_ll import extract_col_majors_from_ll
from extract_dsp_col_majors_from_bit import extract_dsp_col_majors_from_bit
from extract_num_majors_and_minors import extract_num_majors_and_minors
from extract_slr_idcodes import extract_slr_idcodes
from parse_bitstream import parse_bitstream

script_dir_path = Path(__file__).parent.resolve()
tcl_dir_path = script_dir_path / "tcl"

tcl_empty_design = tcl_dir_path / "empty_design.tcl"
tcl_extract_device_info = tcl_dir_path / "extract_device_info.tcl"
tcl_gen_bitstream_from_dcp = tcl_dir_path / "gen_bitstream_from_dcp.tcl"
tcl_one_bram_in_every_bram_column = tcl_dir_path / "one_bram_in_every_bram_column.tcl"
tcl_one_ff_in_every_clb_column = tcl_dir_path / "one_ff_in_every_clb_column.tcl"
tcl_one_dsp_in_every_dsp_column = tcl_dir_path / "one_dsp_in_every_dsp_column.tcl"

# Creates a device summary and automatically writes it to the appropriate place in the resources/ directory.
# The summary is also returned.
def create_device_summary(
  fpga_part: str,
  working_dir: str | Path
) -> dict[str, typing.Any]:
  dir_path = Path(working_dir).resolve()

  # tcl script
  device_info_path = extract_device_info(fpga_part, dir_path)
  if device_info_path is None:
    print(f"Could not extract device info. Exiting...")
    exit(0)

  # tcl script
  empty_bitstream_path = create_empty_bitstream(fpga_part, dir_path)
  if empty_bitstream_path is None:
    print(f"Could not create empty bitstream. Exiting...")
    exit(0)

  # tcl script
  per_frame_crc_bitstream_path = create_per_frame_crc_bitstream(fpga_part, dir_path)
  if per_frame_crc_bitstream_path is None:
    print(f"Could not create per-frame CRC bitstream. Exiting...")
    exit(0)

  per_frame_crc_bitstream_dump_path = per_frame_crc_bitstream_path.parent / f"{per_frame_crc_bitstream_path.name}.dump"
  if not per_frame_crc_bitstream_dump_path.exists():
    parse_bitstream(per_frame_crc_bitstream_path, per_frame_crc_bitstream_dump_path)

  fars_path = dir_path / "fars.csv"
  if not fars_path.exists():
    extract_all_frame_addresses(per_frame_crc_bitstream_path, fars_path)

  idcodes_path = dir_path / "slr_idcodes.json"
  if not idcodes_path.exists():
    extract_slr_idcodes(per_frame_crc_bitstream_path, device_info_path, idcodes_path)

  num_majors_and_minors_path = dir_path / "num_majors_and_minors.json"
  if not num_majors_and_minors_path.exists():
    extract_num_majors_and_minors(fars_path, idcodes_path, fpga_part, num_majors_and_minors_path)

  # tcl script
  one_reg_in_every_clb_column_ll_path = create_one_ff_in_every_clb_column(fpga_part, dir_path)
  if one_reg_in_every_clb_column_ll_path is None:
    print(f"Could not create one FF in every CLB column. Exiting...")
    exit(0)

  # tcl script
  one_bram_in_every_bram_column_ll_path = create_one_bram_in_every_bram_column(fpga_part, dir_path)
  if one_bram_in_every_bram_column_ll_path is None:
    print(f"Could not create one BRAM in every BRAM column. Exiting...")
    exit(0)

  clb_col_majors_json_path = dir_path / "clb_col_majors.json"
  if not clb_col_majors_json_path.exists():
    extract_col_majors_from_ll(fpga_part, one_reg_in_every_clb_column_ll_path, "RegLoc", clb_col_majors_json_path)

  bram_col_majors_json_path = dir_path / "bram_col_majors.json"
  if not bram_col_majors_json_path.exists():
    extract_col_majors_from_ll(fpga_part, one_bram_in_every_bram_column_ll_path, "Bram.*", bram_col_majors_json_path)

  clb_col_tile_types_json_path = dir_path / "clb_col_tile_types.json"
  if not clb_col_tile_types_json_path.exists():
    extract_clb_col_tile_types(device_info_path, clb_col_tile_types_json_path)

  summary = create_summary(
    device_info_path,
    num_majors_and_minors_path,
    clb_col_majors_json_path,
    bram_col_majors_json_path,
    idcodes_path,
    clb_col_tile_types_json_path
  )

  # Temporarily write the summary to its final destination in the resources/ folder.
  # This is because it is easier to extract the DSP columns using the summary rather than many individual files below.
  # Some methods will try to load the summary and they expect it to be in the resources/ folder.
  summary_json_path = resources.get_device_summary_path(fpga_part)
  with open(summary_json_path, "w") as f:
    json_str = format_json.emit(summary, sort_keys=True)
    f.write(json_str)

  # tcl script
  (one_dsp_in_every_dsp_column_bit_path, dsps_json_path) = create_one_dsp_in_every_dsp_column(fpga_part, dir_path)
  if one_dsp_in_every_dsp_column_bit_path is None:
    print(f"Could not create one DSP in every DSP column. Exiting...")
    exit(0)

  dsp_col_majors_json_path = dir_path / "dsp_col_majors.json"
  extract_dsp_col_majors_from_bit(empty_bitstream_path, one_dsp_in_every_dsp_column_bit_path, dsps_json_path, dsp_col_majors_json_path)

  # Create the summary file again now that the DSP major columns has been determined.
  summary = create_summary(
    device_info_path,
    num_majors_and_minors_path,
    clb_col_majors_json_path,
    bram_col_majors_json_path,
    idcodes_path,
    clb_col_tile_types_json_path,
    dsp_col_majors_json_path
  )

  with open(summary_json_path, "w") as f:
    json_str = format_json.emit(summary, sort_keys=True)
    f.write(json_str)

  return summary

# Returns the path to the device info file generated using the given parameters.
# None is returned instead if the file doesn't exist.
def extract_device_info(
  part: str,
  dir_path: Path
) -> Path | None:
  dir_path = dir_path / "device_info"
  dir_path.mkdir(parents=True, exist_ok=True)
  dev_info_path = dir_path / "device_info.json"
  stdout_path = dir_path / "stdout"
  stderr_path = dir_path / "stderr"

  success = helpers.run_script(
    script_path           = tcl_extract_device_info,
    args                  = [part, str(dev_info_path)],
    expected_output_paths = [dev_info_path],
    stdout_path           = stdout_path,
    stderr_path           = stderr_path
  )

  if not success:
    return None
  else:
    return dev_info_path

# Returns the path to an empty bitstream without per-frame CRCs generated using the given parameters.
# None is returned instead if the file doesn't exist.
def create_empty_bitstream(
  part: str,
  dir_path: Path
) -> Path | None:
  dir_path = dir_path / "empty_bitstream"
  dir_path.mkdir(parents=True, exist_ok=True)
  dcp_path = dir_path / "empty.dcp"
  dcp_stdout_path = dir_path / "dcp_stdout"
  dcp_stderr_path = dir_path / "dcp_stderr"
  bit_path = dir_path / "empty_bitstream.bit"
  bit_stdout_path = dir_path / "bit_stdout"
  bit_stderr_path = dir_path / "bit_stderr"

  success_dcp = helpers.run_script(
    script_path           = tcl_empty_design,
    args                  = [part, str(dcp_path)],
    expected_output_paths = [dcp_path],
    stdout_path           = dcp_stdout_path,
    stderr_path           = dcp_stderr_path
  )

  success_bit = helpers.run_script(
    script_path           = tcl_gen_bitstream_from_dcp,
    args                  = [str(dcp_path), str(bit_path)],
    expected_output_paths = [bit_path],
    stdout_path           = bit_stdout_path,
    stderr_path           = bit_stderr_path
  )

  success = success_dcp and success_bit
  if not success:
    return None
  else:
    return bit_path

# Returns the path to the bitstream with per-frame CRCs generated using the given parameters.
# None is returned instead if the file doesn't exist.
def create_per_frame_crc_bitstream(
  part: str,
  dir_path: Path
) -> Path | None:
  dir_path = dir_path / "per_frame_crc_bitstream"
  dir_path.mkdir(parents=True, exist_ok=True)
  dcp_path = dir_path / "empty.dcp"
  dcp_stdout_path = dir_path / "dcp_stdout"
  dcp_stderr_path = dir_path / "dcp_stderr"
  bit_path = dir_path / "per_frame_crc_bitstream.bit"
  bit_stdout_path = dir_path / "bit_stdout"
  bit_stderr_path = dir_path / "bit_stderr"

  success_dcp = helpers.run_script(
    script_path           = tcl_empty_design,
    args                  = [part, str(dcp_path)],
    expected_output_paths = [dcp_path],
    stdout_path           = dcp_stdout_path,
    stderr_path           = dcp_stderr_path
  )

  success_bit = helpers.run_script(
    script_path           = tcl_gen_bitstream_from_dcp,
    args                  = ["-per_frame_crc", str(dcp_path), str(bit_path)],
    expected_output_paths = [bit_path],
    stdout_path           = bit_stdout_path,
    stderr_path           = bit_stderr_path
  )

  success = success_dcp and success_bit
  if not success:
    return None
  else:
    return bit_path

# Returns the path to the logic location file generated using the given parameters.
# None is returned instead if the file doesn't exist.
def create_one_ff_in_every_clb_column(
  part: str,
  dir_path: Path
) -> Path | None:
  dir_path = dir_path / "one_ff_in_every_clb_column"
  dir_path.mkdir(parents=True, exist_ok=True)
  bitstream_path = dir_path / "one_ff_in_every_clb_column.bit"
  logic_loc_path = dir_path / "one_ff_in_every_clb_column.ll"
  stdout_path = dir_path / "stdout"
  stderr_path = dir_path / "stderr"

  success = helpers.run_script(
    script_path           = tcl_one_ff_in_every_clb_column,
    args                  = [part, str(bitstream_path)],
    expected_output_paths = [logic_loc_path],
    stdout_path           = stdout_path,
    stderr_path           = stderr_path
  )

  if not success:
    return None
  else:
    return logic_loc_path

# Returns the path to the logic location file generated using the given parameters.
# None is returned instead if the file doesn't exist.
def create_one_bram_in_every_bram_column(
  part: str,
  dir_path: Path
) -> Path | None:
  dir_path = dir_path / "one_bram_in_every_bram_column"
  dir_path.mkdir(parents=True, exist_ok=True)
  bitstream_path = dir_path / "one_bram_in_every_bram_column.bit"
  logic_loc_path = dir_path / "one_bram_in_every_bram_column.ll"
  stdout_path = dir_path / "stdout"
  stderr_path = dir_path / "stderr"

  success = helpers.run_script(
    script_path           = tcl_one_bram_in_every_bram_column,
    args                  = [part, str(bitstream_path)],
    expected_output_paths = [logic_loc_path],
    stdout_path           = stdout_path,
    stderr_path           = stderr_path
  )

  if not success:
    return None
  else:
    return logic_loc_path

# Returns the path to the bitstream generated using the given parameters, and
# the path to a json file listing the DSPs instantiated (in order).
# None is returned instead if the files do not exist.
def create_one_dsp_in_every_dsp_column(
  part: str,
  dir_path: Path
) -> tuple[
  Path | None, # bitstream path
  Path | None # DSP json path
]:
  dir_path = dir_path / "one_dsp_in_every_dsp_column"
  dir_path.mkdir(parents=True, exist_ok=True)
  bitstream_path = dir_path / "one_dsp_in_every_dsp_column.bit"
  dsps_json_path = dir_path / "dsps.json"
  stdout_path = dir_path / "stdout"
  stderr_path = dir_path / "stderr"

  success = helpers.run_script(
    script_path           = tcl_one_dsp_in_every_dsp_column,
    args                  = [part, str(bitstream_path), str(dsps_json_path)],
    expected_output_paths = [bitstream_path, dsps_json_path],
    stdout_path           = stdout_path,
    stderr_path           = stderr_path
  )

  if not success:
    return (None, None)
  else:
    return (bitstream_path, dsps_json_path)

def create_summary(
  device_info_json_path: Path,
  num_majors_and_minors_json_path: Path,
  clb_majors_json_path: Path,
  bram_majors_json_path: Path,
  idcodes_json_path: Path,
  clb_col_tile_types_json_path: Path,
  # UGLY: This is only used in a 2nd pass in this file as it is easier to reconstruct DSP
  # major columns using the device summary itself. A 2nd pass then feeds the DSP columns
  # to this function to create a new summary that contains the DSP column majors as well.
  dsp_majors_json_path: Path | None = None
) -> dict[str, typing.Any]:
  device_info = helpers.read_json(device_info_json_path)
  num_majors_and_minors = helpers.read_json(num_majors_and_minors_json_path)
  clb_majors = helpers.read_json(clb_majors_json_path)
  bram_majors = helpers.read_json(bram_majors_json_path)
  idcodes = helpers.read_json(idcodes_json_path)
  clb_col_tile_types = helpers.read_json(clb_col_tile_types_json_path)

  if dsp_majors_json_path is None:
    dsp_majors = None
  else:
    dsp_majors = helpers.read_json(dsp_majors_json_path)

  # I want the following dictionary as an output:
  #
  #   {
  #     "part": <name>,
  #     "device": <name>,
  #     "license": (Webpack | Full)
  #     "num_brams": <number>,
  #     "num_dsps": <number>,
  #     "num_regs": <number>,
  #     "num_luts": <number>,
  #     "num_slices": <number>,
  #     "num_slrs": <number>,
  #     "tileType_siteType_pairs": [ ... ]
  #     "slrs": {
  #       "SLR0": {
  #         "idcode": <number>,
  #         "slr_idx": <number>,
  #         "config_order_idx": <number>,
  #         "min_clock_region_row_idx": <number>,
  #         "max_clock_region_row_idx": <number>,
  #         "min_clock_region_col_idx": <number>,
  #         "max_clock_region_col_idx": <number>,
  #         "min_far_row_idx": <number>,
  #         "max_far_row_idx": <number>,
  #         "rowMajors": {
  #           "0": {
  #             "bram_content_colMajors": [ ... ],
  #             "bram_content_parity_colMajors": [ ... ],
  #             "bram_reg_colMajors": [ ... ],
  #             "clb_colMajors": [ ... ],
  #             "dsp_colMajors": [ ... ],
  #             "clb_tileTypes": [ ... ],
  #             "num_minors_per_bram_content_colMajor": [ ... ],
  #             "num_minors_per_std_colMajor": [ ... ],
  #           },
  #           "1": {
  #             ...
  #           }
  #         },
  #     "SLR1": {
  #       ...
  #     }
  #   }
  summary = defaultdict(
    lambda: defaultdict(
      lambda: defaultdict(
        lambda: defaultdict(
          # fields are either lists, dicts, or a single int. We choose list as the general
          # structure and we'll overwrite the entries that are supposed to map to
          # a number later.
          lambda: defaultdict(list)
        )
      )
    )
  )

  # "part": <name>,
  # "device": <name>,
  # "license": (Webpack | Full)
  # "num_brams": <number>,
  # "num_dsps": <number>,
  # "num_regs": <number>,
  # "num_luts": <number>,
  # "num_slices": <number>,
  # "num_slrs": <number>,
  # "tileType_siteType_pairs": [ ... ]
  part_properties = device_info["part_properties"]
  summary["part"] = part_properties["NAME"]
  summary["device"] = part_properties["DEVICE"]
  summary["license"] = part_properties["LICENSE"]
  summary["num_brams"] = part_properties["BLOCK_RAMS"]
  summary["num_dsps"] = part_properties["DSP"]
  summary["num_regs"] = part_properties["FLIPFLOPS"]
  summary["num_luts"] = part_properties["LUT_ELEMENTS"]
  summary["num_slices"] = part_properties["SLICES"]
  summary["num_slrs"] = part_properties["SLRS"]
  summary["tileType_siteType_pairs"] = device_info["tileType_siteType_pairs"]

  part_composition = device_info["composition"]
  for (slrName, slrProperties) in part_composition["slrs"].items():
    # "idcode": <number>,
    # "slr_idx": <number>,
    # "config_order_idx": <number>,
    # "min_clock_region_row_idx": <number>,
    # "max_clock_region_row_idx": <number>,
    # "min_clock_region_col_idx": <number>,
    # "max_clock_region_col_idx": <number>,
    # "min_far_row_idx": <number>,
    # "max_far_row_idx": <number>,
    idcode = idcodes[slrName]
    slr_idx = slrProperties["slr_idx"]
    config_order_idx = slrProperties["config_order_idx"]
    min_clock_region_row_idx = slrProperties["min_clock_region_row_idx"]
    max_clock_region_row_idx = slrProperties["max_clock_region_row_idx"]
    min_clock_region_col_idx = slrProperties["min_clock_region_col_idx"]
    max_clock_region_col_idx = slrProperties["max_clock_region_col_idx"]
    min_far_row_idx = 0
    max_far_row_idx = len(num_majors_and_minors["slrs"][slrName]["rowMajors"]) - 1
    summary["slrs"][slrName]["idcode"] = idcode
    summary["slrs"][slrName]["slr_idx"] = slr_idx
    summary["slrs"][slrName]["config_order_idx"] = config_order_idx
    summary["slrs"][slrName]["min_clock_region_row_idx"] = min_clock_region_row_idx
    summary["slrs"][slrName]["max_clock_region_row_idx"] = max_clock_region_row_idx
    summary["slrs"][slrName]["min_clock_region_col_idx"] = min_clock_region_col_idx
    summary["slrs"][slrName]["max_clock_region_col_idx"] = max_clock_region_col_idx
    summary["slrs"][slrName]["min_far_row_idx"] = min_far_row_idx
    summary["slrs"][slrName]["max_far_row_idx"] = max_far_row_idx

    # The device may have more "rows" in its FAR numbering scheme than it has
    # official clock region "rows". It is important to store both and to use the
    # FAR row count when generating the device summary so other classes that
    # try to locate BELs on the device can do it correctly.
    slr_rowMajors = range(0, max_far_row_idx + 1)
    for rowMajor_int in slr_rowMajors:
      rowMajor_str = str(rowMajor_int)

      # This entry should only exist for "real" clock regions (not hidden ones).
      # "bram_content_colMajors": [ ... ],
      bram_mem_rowMajorProperties = bram_majors["slrs"][slrName]["BramMemLoc"]["rowMajors"].get(rowMajor_str)
      if bram_mem_rowMajorProperties is not None:
        bram_mem_colMajors = bram_mem_rowMajorProperties["colMajors"]
        summary["slrs"][slrName]["rowMajors"][rowMajor_str]["bram_content_colMajors"] = bram_mem_colMajors

      # This entry should only exist for "real" clock regions (not hidden ones).
      # "bram_content_parity_colMajors": [ ... ],
      bram_mem_parity_rowMajorProperties = bram_majors["slrs"][slrName]["BramMemParityLoc"]["rowMajors"].get(rowMajor_str)
      if bram_mem_parity_rowMajorProperties is not None:
        bram_mem_parity_colMajors = bram_mem_parity_rowMajorProperties["colMajors"]
        summary["slrs"][slrName]["rowMajors"][rowMajor_str]["bram_content_parity_colMajors"] = bram_mem_parity_colMajors

      # This entry should only exist for "real" clock regions (not hidden ones).
      # "bram_reg_colMajors": [ ... ],
      bram_reg_rowMajorProperties = bram_majors["slrs"][slrName]["BramRegLoc"]["rowMajors"].get(rowMajor_str)
      if bram_reg_rowMajorProperties is not None:
        bram_reg_colMajors = bram_reg_rowMajorProperties["colMajors"]
        summary["slrs"][slrName]["rowMajors"][rowMajor_str]["bram_reg_colMajors"] = bram_reg_colMajors

      # This entry should only exist for "real" clock regions (not hidden ones).
      # "dsp_colMajors": [ ... ],
      #
      # Recall that DSP information is not always fed to the device summary creation function. Check
      # comment at top of this function for background.
      if dsp_majors is not None:
        dsp_majors_rowMajorProperties = dsp_majors["slrs"][slrName]["DSP"]["rowMajors"].get(rowMajor_str)
        if dsp_majors_rowMajorProperties is not None:
          dsp_colMajors = dsp_majors_rowMajorProperties["colMajors"]
          dsp_bottom_y = dsp_majors_rowMajorProperties["min_dsp_y_ofst"]
          dsp_top_y = dsp_majors_rowMajorProperties["max_dsp_y_ofst"]
          summary["slrs"][slrName]["rowMajors"][rowMajor_str]["dsp_colMajors"] = dsp_colMajors
          summary["slrs"][slrName]["rowMajors"][rowMajor_str]["min_dsp_y_ofst"] = dsp_bottom_y
          summary["slrs"][slrName]["rowMajors"][rowMajor_str]["max_dsp_y_ofst"] = dsp_top_y

      # This entry should only exist for "real" clock regions (not hidden ones).
      # "clb_colMajors": [ ... ],
      clb_majors_rowMajorProperties = clb_majors["slrs"][slrName]["RegLoc"]["rowMajors"].get(rowMajor_str)
      if clb_majors_rowMajorProperties is not None:
        clb_colMajors = clb_majors_rowMajorProperties["colMajors"]
        summary["slrs"][slrName]["rowMajors"][rowMajor_str]["clb_colMajors"] = clb_colMajors

      # This entry should only exist for "real" clock regions (not hidden ones).
      # "clb_tileTypes": [ ... ],
      clb_tileTypes_rowMajorProperties = clb_col_tile_types["slrs"][slrName]["rowMajors"].get(rowMajor_str)
      if clb_tileTypes_rowMajorProperties is not None:
        clb_tileTypes = clb_tileTypes_rowMajorProperties["clb_tileTypes"]
        summary["slrs"][slrName]["rowMajors"][rowMajor_str]["clb_tileTypes"] = clb_tileTypes

      # This entry exists for ALL clock regions (including hidden ones).
      # "num_minors_per_bram_content_colMajor": [ ... ],
      num_minors_per_bram_colMajor = num_majors_and_minors["slrs"][slrName]["rowMajors"][rowMajor_str]["num_minors_per_bram_colMajor"]
      summary["slrs"][slrName]["rowMajors"][rowMajor_str]["num_minors_per_bram_content_colMajor"] = num_minors_per_bram_colMajor

      # This entry exists for ALL clock regions (including hidden ones).
      # "num_minors_per_std_colMajor": [ ... ],
      num_minors_per_std_colMajor = num_majors_and_minors["slrs"][slrName]["rowMajors"][rowMajor_str]["num_minors_per_std_colMajor"]
      summary["slrs"][slrName]["rowMajors"][rowMajor_str]["num_minors_per_std_colMajor"] = num_minors_per_std_colMajor

  return summary

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Creates a summary description of part-specific metrics needed to compute frame addresses.")
  parser.add_argument("fpga_part", type=str, help="FPGA part number.")
  parser.add_argument("working_dir", type=str, help="Working directory (for intermediate output files).")
  parser.add_argument("out_json", type=str, help="Output JSON file containing device summary.")
  args = parser.parse_args()

  summary = create_device_summary(args.fpga_part, args.working_dir, args.out_json)

  with open(args.out_json, "w") as f:
    json_str = format_json.emit(summary, sort_keys=True)
    f.write(json_str)

  print("Done")
