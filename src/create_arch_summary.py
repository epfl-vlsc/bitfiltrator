# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
import re
import typing
from collections import defaultdict
from pathlib import Path

import joblib

import format_json
import helpers
import resources
from arch_spec import ArchSpec
from extract_encoding_from_logic_loc import extract_encoding_from_logic_loc
from lut_init_sweep_to_logic_loc import lut_init_sweep_to_logic_loc

script_dir_path = Path(__file__).parent.resolve()
tcl_dir_path = script_dir_path / "tcl"

tcl_all_brams_in_one_bram_column = tcl_dir_path / "all_brams_in_one_bram_column.tcl"
tcl_all_ffs_in_one_clb_column = tcl_dir_path / "all_ffs_in_one_clb_column.tcl"
tcl_all_lutrams_in_one_clb_column = tcl_dir_path / "all_lutrams_in_one_clb_column.tcl"
tcl_all_luts_in_one_clb_column = tcl_dir_path / "all_luts_in_one_clb_column.tcl"
tcl_sweep_lut_init = tcl_dir_path / "sweep_lut_init.tcl"

# Creates an architecture summary and automatically writes it to the appropriate place in the resources/ directory.
# The summary is also returned.
def create_arch_summary(
  part: str,
  working_dir : str | Path,
  process_cnt: int = 1
) -> dict[str, typing.Any]:
  dir_path = Path(working_dir).resolve()

  device_summary = resources.get_device_summary(part)
  tileType_siteType_pairs = device_summary.tileType_siteType_pairs
  tile_encodings = extract_tile_encodings(dir_path, part, tileType_siteType_pairs, process_cnt)

  # Write the arch summary to its intended location in the resources/ directory.
  # Additionally write the summary to where the user is asking.
  summary_json_path = resources.get_arch_summary_path(part)
  with open(summary_json_path, "w") as f:
    json_str = format_json.emit(tile_encodings, sort_keys=True)
    f.write(json_str)

  return tile_encodings

# Returns the path to the logic location file generated using the given parameters.
# None is returned instead if the file doesn't exist.
def create_all_ffs_in_one_clb_column(
  part: str,
  tile_type: str,
  dir_path: Path
) -> Path | None:
  dir_path = dir_path / "all_ffs_in_one_clb_column"
  dir_path.mkdir(parents=True, exist_ok=True)
  bitstream_path = dir_path / "all_ffs_in_one_clb_column.bit"
  logic_loc_path = dir_path / "all_ffs_in_one_clb_column.ll"
  stdout_path = dir_path / "stdout"
  stderr_path = dir_path / "stderr"

  success = helpers.run_script(
    script_path           = tcl_all_ffs_in_one_clb_column,
    args                  = [part, tile_type, str(bitstream_path)],
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
def create_all_lutrams_in_one_clb_column(
  part: str,
  tile_type: str,
  dir_path: Path
) -> Path | None:
  dir_path = dir_path / "all_lutrams_in_one_clb_column"
  dir_path.mkdir(parents=True, exist_ok=True)
  bitstream_path = dir_path / "all_lutrams_in_one_clb_column.bit"
  logic_loc_path = dir_path / "all_lutrams_in_one_clb_column.ll"
  stdout_path = dir_path / "stdout"
  stderr_path = dir_path / "stderr"

  success = helpers.run_script(
    script_path           = tcl_all_lutrams_in_one_clb_column,
    args                  = [part, tile_type, str(bitstream_path)],
    expected_output_paths = [logic_loc_path],
    stdout_path           = stdout_path,
    stderr_path           = stderr_path
  )

  if not success:
    return None
  else:
    return logic_loc_path

# Returns the path to the design checkpoint file and bitstream generated using the given parameters.
# None is returned instead if the file doesn't exist.
def create_all_luts_in_one_clb_column(
  part: str,
  tile_type: str,
  dir_path: Path
) -> tuple[
  Path, # DCP
  Path  # Bitstream
] | None:
  dir_path = dir_path / "all_luts_in_one_clb_column"
  dir_path.mkdir(parents=True, exist_ok=True)
  bitstream_path = dir_path / "all_luts_in_one_clb_column.bit"
  dcp_path = dir_path / "all_luts_in_one_clb_column.dcp"
  stdout_path = dir_path / "stdout"
  stderr_path = dir_path / "stderr"

  success = helpers.run_script(
    script_path           = tcl_all_luts_in_one_clb_column,
    args                  = [part, tile_type, str(bitstream_path)],
    expected_output_paths = [bitstream_path, dcp_path],
    stdout_path           = stdout_path,
    stderr_path           = stderr_path
  )

  if not success:
    return None
  else:
    return (dcp_path, bitstream_path)

# Returns the path to the directory containing lut equation sweep bitstreams.
def sweep_lut_init(
  dcp_path: Path,
  lut_idx_low: int,
  lut_idx_high: int,
  dir_path: Path
) -> Path | None:

  def get_expected_artifact_paths(dir_path: Path):
    paths = list()

    for lut_idx in range(lut_idx_low, lut_idx_high + 1):
      for bit_idx in range(0, 64):
        # The bit_idx is for a one-hot binary representation and idx 0 corresponds to
        # the right-most element of the list, hence why we reverse the output.
        bin_equation = "".join(reversed(["0" if i != bit_idx else "1" for i in range(0, 64)]))
        fname_wo_extension_path = dir_path / f"lut_gen[{lut_idx}].lut6_inst_b{bin_equation}"
        # The bitstreams are compressed to save space (hence the .gz extension), but the design
        # checkpoints are not.
        bitstream_path = fname_wo_extension_path.parent / f"{fname_wo_extension_path.name}.bit.gz"
        checkpoint_path = fname_wo_extension_path.parent / f"{fname_wo_extension_path.name}.dcp"
        paths.append(bitstream_path)
        paths.append(checkpoint_path)

    return paths

  dir_path = dir_path / "sweep_lut_init"
  dir_path.mkdir(parents=True, exist_ok=True)
  expected_output_paths = get_expected_artifact_paths(dir_path)
  stdout_path = dir_path / "stdout"
  stderr_path = dir_path / "stderr"

  success = helpers.run_script(
    script_path           = tcl_sweep_lut_init,
    args                  = [str(dcp_path), str(lut_idx_low), str(lut_idx_high), str(dir_path)],
    expected_output_paths = expected_output_paths,
    stdout_path           = stdout_path,
    stderr_path           = stderr_path
  )

  if not success:
    return None
  else:
    return dir_path

def sweep_lut_init_batch(
  dcp_path: Path,
  lut_idx_low: int,
  lut_idx_high: int,
  dir_path: Path,
  process_cnt: int
) -> Path:
  bitstream_dirs = joblib.Parallel(
    n_jobs=process_cnt,
    verbose=10
  )(
    # Every process takes care of 1 LUT completely.
    joblib.delayed(sweep_lut_init)(dcp_path, lut_idx, lut_idx, dir_path) for lut_idx in range(lut_idx_low, lut_idx_high + 1)
  )

  # We are using the same bitstream directory for everyone, so we can just select
  # the first entry.
  return bitstream_dirs[0]

# Returns the path to the logic location file generated using the given parameters.
# None is returned instead if the file doesn't exist.
def create_all_brams_in_one_bram_column(
  part: str,
  dir_path: Path
) -> Path | None:
  dir_path = dir_path / "all_brams_in_one_bram_column"
  dir_path.mkdir(parents=True, exist_ok=True)
  bitstream_path = dir_path / "all_brams_in_one_bram_column.bit"
  logic_loc_path = dir_path / "all_brams_in_one_bram_column.ll"
  stdout_path = dir_path / "stdout"
  stderr_path = dir_path / "stderr"

  success = helpers.run_script(
    script_path           = tcl_all_brams_in_one_bram_column,
    args                  = [part, str(bitstream_path)],
    expected_output_paths = [logic_loc_path],
    stdout_path           = stdout_path,
    stderr_path           = stderr_path
  )

  if not success:
    return None
  else:
    return logic_loc_path

def extract_tile_encodings(
  dir_path: Path,
  part: str,
  tileType_siteType_pairs: list[tuple[str, str]],
  process_cnt: int
) -> dict[str, typing.Any]:

  def offset_lut_encodings(
    single_clb_lut_encoding: dict[str, typing.Any],
    all_ff_encoding: dict[str, typing.Any],
    out_json: str | Path
  ) -> dict[str, typing.Any]:
    # The LUTs we extracted are in CLB 0 (bottom-most CLB of a column).
    # JSON keys are string, hence the str(0)
    orig_lut_frame_ofsts: dict[str, list[int]] = single_clb_lut_encoding["LutLoc"]["Y_ofst"][str(0)]["frame_ofst"] # lut_name -> frame_ofsts
    orig_lut_minors: dict[str, list[int]] = single_clb_lut_encoding["LutLoc"]["Y_ofst"][str(0)]["minor"] # lut_name -> minors

    lut_names = orig_lut_frame_ofsts.keys()

    # We use AFF in CLB0 as the original anchor.
    anchor_name = "AFF"
    # JSON keys are string, hence the str(0)
    orig_anchor_frame_ofst: int = all_ff_encoding["RegLoc"]["Y_ofst"][str(0)]["frame_ofst"][anchor_name]
    orig_anchor_minor: int = all_ff_encoding["RegLoc"]["Y_ofst"][str(0)]["minor"][anchor_name]

    # Compute translation offsets from the isolated CLB's LUTs to the original anchor.
    orig_lut_to_orig_anchor_frame_ofst_diffs = dict[str, list[int]]()
    orig_lut_to_orig_anchor_minor_diffs = dict[str, list[int]]()
    for lut_name in lut_names:
      orig_lut_to_orig_anchor_frame_ofst_diffs[lut_name] = [orig_anchor_frame_ofst - orig_lut_frame_ofst for orig_lut_frame_ofst in orig_lut_frame_ofsts[lut_name]]
      orig_lut_to_orig_anchor_minor_diffs[lut_name] = [orig_anchor_minor - orig_lut_minor for orig_lut_minor in orig_lut_minors[lut_name]]

    # We want the resulting dictionary to look like this:
    #
    # "LutLoc": {
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
    # }
    encoding = defaultdict(
      lambda: defaultdict(
        lambda: defaultdict(
          lambda: defaultdict(
            lambda: defaultdict(list)
          )
        )
      )
    )

    # Translate the frame_ofst/minors of LUTs to the same anchor in the other CLBs.
    # This is done by finding the original-to-new anchor translation offset.
    # Then we simply add this translation offset to the LUTs' frame offset and minor.
    for y_ofst_str in all_ff_encoding["RegLoc"]["Y_ofst"]:
      new_anchor_frame_ofst: int = all_ff_encoding["RegLoc"]["Y_ofst"][y_ofst_str]["frame_ofst"][anchor_name]
      new_anchor_minor: int = all_ff_encoding["RegLoc"]["Y_ofst"][y_ofst_str]["minor"][anchor_name]

      orig_to_new_anchor_frame_ofst_diff = new_anchor_frame_ofst - orig_anchor_frame_ofst
      orig_to_new_anchor_minor_diff = new_anchor_minor - orig_anchor_minor

      for lut_name in lut_names:
        lut_name_orig_frame_ofsts = orig_lut_frame_ofsts[lut_name]
        lut_name_orig_minors = orig_lut_minors[lut_name]
        encoding["LutLoc"]["Y_ofst"][y_ofst_str]["frame_ofst"][lut_name] = [lut_name_orig_frame_ofst + orig_to_new_anchor_frame_ofst_diff for lut_name_orig_frame_ofst in lut_name_orig_frame_ofsts]
        encoding["LutLoc"]["Y_ofst"][y_ofst_str]["minor"][lut_name] = [lut_name_orig_minor + orig_to_new_anchor_minor_diff for lut_name_orig_minor in lut_name_orig_minors]

    with open(out_json, "w") as f:
      json_str = format_json.emit(encoding, sort_keys=True)
      f.write(json_str)


  ar_spec = ArchSpec.create_spec(part)

  tile_encodings = dict()

  slicemTileTypes: list[str] = sorted(set([
    tile_type
    for (tile_type, site_type) in tileType_siteType_pairs
    if re.search(r"SLICEM", site_type) is not None
  ]))
  slicelTileTypes: list[str] = sorted(set([
    tile_type
    for (tile_type, site_type) in tileType_siteType_pairs
    if re.search("SLICEL", site_type) is not None
  ]))
  bramTileTypes: list[str] = sorted(set([
    tile_type
    for (tile_type, site_type) in tileType_siteType_pairs
    if re.search(r"RAMB.*", site_type) is not None
  ]))

  print(f"Candidate SLICEM tile types = {slicemTileTypes}")
  print(f"Candidate SLICEL tile types = {slicelTileTypes}")
  print(f"Candidate BRAM tile types = {bramTileTypes}")

  for tile_type in slicemTileTypes:
    print(f"Extracting encoding of tile type \"{tile_type}\"")
    tile_type_path = dir_path / tile_type

    all_ffs_in_one_clb_column_ll_path = create_all_ffs_in_one_clb_column(part, tile_type, tile_type_path)
    ff_encoding_json_path = tile_type_path / "ff_encoding.json"
    extract_encoding_from_logic_loc(all_ffs_in_one_clb_column_ll_path, part, ff_encoding_json_path, "^RegLoc$")
    ff_encoding = helpers.read_json(ff_encoding_json_path)

    all_lutrams_in_one_clb_column_ll_path = create_all_lutrams_in_one_clb_column(part, tile_type, tile_type_path)
    lutram_encoding_json_path = tile_type_path / "lutram_encoding.json"
    extract_encoding_from_logic_loc(all_lutrams_in_one_clb_column_ll_path, part, lutram_encoding_json_path, "^LutramLoc$")
    lutram_encoding = helpers.read_json(lutram_encoding_json_path)

    tile_encodings[tile_type] = ff_encoding | lutram_encoding

  for tile_type in slicelTileTypes:
    print(f"Extracting encoding of tile type \"{tile_type}\"")
    tile_type_path = dir_path / tile_type

    all_ffs_in_one_clb_column_ll_path = create_all_ffs_in_one_clb_column(part, tile_type, tile_type_path)
    ff_encoding_json_path = tile_type_path / "ff_encoding.json"
    extract_encoding_from_logic_loc(all_ffs_in_one_clb_column_ll_path, part, ff_encoding_json_path, "^RegLoc$")
    ff_encoding = helpers.read_json(ff_encoding_json_path)

    (all_luts_in_one_clb_column_dcp_path, all_luts_in_one_clb_column_bitstream_path) = create_all_luts_in_one_clb_column(part, tile_type, tile_type_path)
    # Fuzz the encoding of the LUTs in the bottom-most CLB of the column.
    (lut_idx_low, lut_idx_high) = (0, ar_spec.num_lut_per_clb() - 1)
    lut_init_sweep_bitstream_dir_path = sweep_lut_init_batch(all_luts_in_one_clb_column_dcp_path, lut_idx_low, lut_idx_high, tile_type_path, process_cnt)
    all_luts_in_one_clb_column_ll_path = tile_type_path / "single_clb_lut_encoding.ll"
    lut_init_sweep_to_logic_loc(all_luts_in_one_clb_column_bitstream_path, lut_init_sweep_bitstream_dir_path, all_luts_in_one_clb_column_ll_path, ".*\.bit\.gz", process_cnt)
    single_clb_lut_encoding_json_path = tile_type_path / "single_clb_lut_encoding.json"
    extract_encoding_from_logic_loc(all_luts_in_one_clb_column_ll_path, part, single_clb_lut_encoding_json_path, "^LutLoc$")
    single_clb_lut_encoding = helpers.read_json(single_clb_lut_encoding_json_path)
    all_clb_lut_encoding_json_path = tile_type_path / "all_clb_lut_encoding.json"
    offset_lut_encodings(single_clb_lut_encoding, ff_encoding, all_clb_lut_encoding_json_path)
    all_clb_lut_encoding = helpers.read_json(all_clb_lut_encoding_json_path)

    tile_encodings[tile_type] = ff_encoding | all_clb_lut_encoding

  for tile_type in bramTileTypes:
    print(f"Extracting encoding of tile type \"{tile_type}\"")
    tile_type_path = dir_path / tile_type

    all_brams_in_one_bram_column_ll_path = create_all_brams_in_one_bram_column(part, tile_type_path)
    bram_encoding_json_path = tile_type_path / "bram_encoding.json"
    extract_encoding_from_logic_loc(all_brams_in_one_bram_column_ll_path, part, bram_encoding_json_path, "^BramMem.*Loc$")
    bram_encoding = helpers.read_json(bram_encoding_json_path)

    tile_encodings[tile_type] = bram_encoding

  return tile_encodings

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Creates a summary description of arch-specific metrics needed to compute a minor address and a frame offset.")
  parser.add_argument("fpga_part", type=str, help="FPGA part number.")
  parser.add_argument("working_dir", type=str, help="Working directory (for intermediate output files).")
  parser.add_argument("out_json", type=str, help="Output JSON file containing arch summary.")
  parser.add_argument("--process_cnt", type=int, default=1, help="Joblib parallelism (use -1 to use all cores).")
  args = parser.parse_args()

  summary = create_arch_summary(args.fpga_part, args.working_dir, args.process_cnt)

  with open(args.out_json, "w") as f:
    json_str = format_json.emit(summary, sort_keys=True)
    f.write(json_str)

  print("Done")
