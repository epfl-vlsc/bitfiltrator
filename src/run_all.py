# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
from collections import defaultdict
from pathlib import Path
from pprint import pprint

import joblib

import helpers
import resources
from arch_names import ArchName
from bitstream_state_checker import check_state
from create_arch_summary import create_arch_summary
from create_device_summary import create_device_summary
from generate_fpga_part_files import generate_fpga_part_files

script_dir_path = Path(__file__).parent.resolve()
tcl_dir_path = script_dir_path / "tcl"

tcl_fill_fpga = tcl_dir_path / "fill_fpga.tcl"
tcl_gen_bitstream_from_dcp = tcl_dir_path / "gen_bitstream_from_dcp.tcl"

# Returns:
# - part_archShortName_dict
# - part_partTargetDir_dict
# - archShortName_archTargetDir_dict
def get_ultrascale_bitstream_candidates(
  target_dir_path: Path
) -> tuple[
  # part -> arch
  dict[str, str],
  # part -> part_target_dir
  dict[str, Path],
  # arch -> arch_target_dir
  dict[str, Path]
]:
  print("Enumerating bitstream candidates")

  # { arch -> { device -> list[fpga_part, ...] } }
  archs_dict: dict[ArchName, dict[str, list[str]]] = defaultdict(
    lambda: defaultdict(list)
  )
  # We limit ourselves to webpack devices as we can always generate bitstreams
  # for such devices.
  for fpga_part in resources.get_webpack_parts():
    (device, arch) = resources.get_device_and_arch(fpga_part)
    archs_dict[arch][device].append(fpga_part)

  part_arch_dict = dict()
  part_partTargetDir_dict = dict()
  arch_archTargetDir_dict = dict()
  for (arch, device_parts_dict) in archs_dict.items():
    for device in sorted(device_parts_dict):
      parts = device_parts_dict[device]
      if parts != []:
        # We just select the first fpga_part for every device as the parts of a device
        # only differ in speed/pins, not in internal layout.
        # We sort the fpga_parts before taking the first entry to ensure deterministic
        # execution.
        first_part = sorted(parts)[0]
        arch_dir_path = target_dir_path / arch.name
        part_dir_path = arch_dir_path / device
        part_arch_dict[first_part] = arch
        part_partTargetDir_dict[first_part] = part_dir_path
        arch_archTargetDir_dict[arch] = arch_dir_path

  pprint(part_arch_dict)
  pprint(part_partTargetDir_dict)
  pprint(arch_archTargetDir_dict)

  return (part_arch_dict, part_partTargetDir_dict, arch_archTargetDir_dict)

# Runs all steps needed to get artifacts for a single FPGA part.
def run_part(
  part: str,
  dir_path: Path
) -> None:
  print(f"Extracting part-specific information for \"{part}\"")
  create_device_summary(part, dir_path)

def run_part_batch(
  part_partPath: dict[str, Path],
  process_cnt: int
) -> None:
  joblib.Parallel(
    n_jobs=process_cnt,
    verbose=10
  )(
    joblib.delayed(run_part)(part, part_path) for (part, part_path) in part_partPath.items()
  )

def run_arch(
  part: str,
  dir_path: Path,
  process_cnt: int
) -> dict[str, Path]:
  print(f"Extracting arch-specific information for \"{part}\"")
  create_arch_summary(part, dir_path, process_cnt)

# Creates a bitstream filled with LUTs, FFs, and BRAMs.
# Each resource is initialized with a random INIT value.
# A JSON file is returned with the bitstream that describes
# what the INIT values are.
def create_filled_bitstream(
  part: str,
  dir_path: Path
) -> tuple[
  Path | None, # bitstream_path
  Path | None # json_path
]:
  dir_path = dir_path / part
  dir_path.mkdir(parents=True, exist_ok=True)

  dcp_path = dir_path / "filled.dcp"
  bit_path = dir_path / "filled.bit"
  expected_json_path = dir_path / "filled.json"
  dcp_stdout_path = dir_path / "dcp_stdout"
  dcp_stderr_path = dir_path / "dcp_stderr"
  bit_stdout_path = dir_path / "bit_stdout"
  bit_stderr_path = dir_path / "bit_stderr"

  success_dcp = helpers.run_script(
    script_path           = tcl_fill_fpga,
    args                  = [part, str(dcp_path), str(expected_json_path)],
    expected_output_paths = [dcp_path, expected_json_path],
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
    return (None, None)
  else:
    return (bit_path, expected_json_path)

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Reverse engineers Xilinx UltraScale/UltraScale+ device and architecture constants for all WebPack FPGAs in your Vivado installation.")
  parser.add_argument("working_dir", type=str, help="Working directory (for intermediate output files).")
  parser.add_argument("--verify", action="store_true", help="If present, verifies the reverse-engineered parameters after extraction. This involves generating bitstreams with random LUT/FF/BRAM data and reconstructing them. This can take ~30m for a single large device! We recommend using --process_cnt to check multiple bitstreams concurrently.")
  parser.add_argument("--process_cnt", type=int, default=1, help="Joblib parallelism (use -1 to use all cores).")
  args = parser.parse_args()

  target_dir_path = Path(args.working_dir).resolve()

  generate_fpga_part_files()
  resources.load_part_files()

  (part_archShortName, part_partTargetDir, archShortName_archTargetDir) = get_ultrascale_bitstream_candidates(target_dir_path)

  ######################################################################################################################
  # Reverse-engineer device parameters.
  ######################################################################################################################

  run_part_batch(part_partTargetDir, args.process_cnt)

  ######################################################################################################################
  # Reverse-engineer architecture parameters.
  ######################################################################################################################

  part_summary = {part: resources.get_device_summary(part) for part in part_partTargetDir}

  for (archShortName, archTargetDir) in archShortName_archTargetDir.items():
    # We select the smallest part in each architecture for these experiments to reduce compile times.
    smallest_part = min(
      [part for (part, arch) in part_archShortName.items() if arch == archShortName],
      key=lambda part: part_summary[part].num_luts
    )
    print(f"{archShortName} -> smallest_part is {smallest_part}")
    run_arch(smallest_part, archTargetDir, args.process_cnt)

  ######################################################################################################################
  # Check device and architecture parameters.
  ######################################################################################################################

  if args.verify:
    verify_path = target_dir_path / "verify"

    bitstreamPath_expectedValuesJsonPath_list = joblib.Parallel(
      n_jobs=args.process_cnt,
      verbose=10
    )(
      joblib.delayed(create_filled_bitstream)(part, verify_path) for part in part_partTargetDir
    )

    check_statuses = joblib.Parallel(
      n_jobs=args.process_cnt,
      verbose=10
    )(
      joblib.delayed(check_state)(bitstream_path, expected_values_json_path) for (bitstream_path, expected_values_json_path) in bitstreamPath_expectedValuesJsonPath_list
    )

    if all(check_statuses):
      print("All checks passed!")
    else:
      print("Some checks failed!")

  print("Done")