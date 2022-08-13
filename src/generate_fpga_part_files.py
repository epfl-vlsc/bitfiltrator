# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
from pathlib import Path

import helpers
import resources

script_dir_path = Path(__file__).parent.resolve()
tcl_dir_path = script_dir_path / "tcl"

tcl_get_parts = tcl_dir_path / "get_parts.tcl"

# Creates json files categorizing all parts by their architecture/device.
def generate_fpga_part_files():
  print("Creating part files")

  all_parts_path = resources.PARTS_ALL_FILE
  webpack_parts_path = resources.PARTS_WEBPACK_FILE

  helpers.run_script(
    script_path=tcl_get_parts,
    args=[".*ultrascale.*", str(all_parts_path)],
    expected_output_paths=[all_parts_path]
  )

  helpers.run_script(
    script_path=tcl_get_parts,
    args=["-keep_webpack_only", ".*ultrascale.*", str(webpack_parts_path)],
    expected_output_paths=[webpack_parts_path]
  )

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Generates FPGA part files by calling Vivado.")
  args = parser.parse_args()

  generate_fpga_part_files()

  print("Done")