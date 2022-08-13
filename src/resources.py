# author: Sahand Kashani <sahand.kashani@epfl.ch>

import re
from pathlib import Path

import helpers
from arch_names import ArchName
from arch_summary import ArchSummary
from device_summary import DeviceSummary

# We want the resources to be at the same level as the README in the repository, hence why
# there are two calls to `parent`.
RESOURCES_DIR = Path(__file__).parent.parent.resolve() / "resources"
RESOURCES_DIR.mkdir(parents=True, exist_ok=True)

DEVICE_SUMMARY_DIR = RESOURCES_DIR / "devices"
DEVICE_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

ARCH_SUMMARY_DIR = RESOURCES_DIR / "archs"
ARCH_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

PARTS_ALL_FILE = RESOURCES_DIR / "parts_all.json"
PARTS_WEBPACK_FILE = RESOURCES_DIR / "parts_webpack.json"

# part -> (device, arch)
_parts_all_db: dict[str, tuple[str, ArchName]] = dict()
_parts_webpack_db: dict[str, tuple[str, ArchName]] = dict()

# device -> DeviceSummary
_device_summaries: dict[str, DeviceSummary] = dict()

# ArchName -> ArchSummary
_arch_summaries: dict[ArchName, ArchSummary] = dict()

def load_part_files() -> None:
  # Parses a file containing all known FPGA parts. Associates each FPGA part with
  # its device name and architecture name.
  #
  # The same device exists in various speed grades and packaging options, so there
  # are multiple parts per device. The list below shows all existing parts for
  # device xcu250 at the time of this writing.
  #
  #     xcu250-figd2104-2-e
  #     xcu250-figd2104-2L-e
  #     xcu250-figd2104-2LV-e
  #
  # The architecture of the device above is "Virtex UltraScale+". We simplify to
  # an enum.
  def load_part_file(
    path: Path
  ) -> dict[
    str, # part
    tuple[
      str, # device
      ArchName # arch
    ]
  ]:
    config_dict = helpers.read_json(path)

    # part -> (device, arch)
    part_deviceArch: dict[str, tuple[str, ArchName]] = dict()

    for (arch, devices_dict) in config_dict.items():
      for (device, parts_list) in devices_dict.items():
        for part in parts_list:

          if re.search(r"ultrascale\+", arch, re.IGNORECASE):
            part_deviceArch[part] = (device, ArchName.ULTRASCALE_PLUS)
          elif re.search(r"ultrascale", arch, re.IGNORECASE):
            part_deviceArch[part] = (device, ArchName.ULTRASCALE)

    return part_deviceArch


  # Done so the resources are just loaded once and not repetitively in multiple places (they are heavy).
  global _parts_all_db
  global _parts_webpack_db

  if len(_parts_all_db) == 0:
    _parts_all_db = load_part_file(PARTS_ALL_FILE)

  if len(_parts_webpack_db) == 0:
    _parts_webpack_db = load_part_file(PARTS_WEBPACK_FILE)

def get_device_and_arch(
  fpga_part: str
) -> tuple[str, ArchName]:
  load_part_files()
  (device, arch) = _parts_all_db[fpga_part]
  return (device, arch)

def get_device_summary_path(
  fpga_part: str
) -> Path:
  (device, arch) = get_device_and_arch(fpga_part)
  return DEVICE_SUMMARY_DIR / f"{device}.json"

def get_device_summary(
  fpga_part: str
) -> DeviceSummary:
  (device, arch) = get_device_and_arch(fpga_part)

  global _device_summaries
  if device not in _device_summaries:
    summary_path = get_device_summary_path(fpga_part)
    _device_summaries[device] = DeviceSummary(helpers.read_json(summary_path))

  return _device_summaries[device]

# Returns the path to the architecture file for the given part.
# None is returned if the architecture is unknown.
def get_arch_summary_path(
  fpga_part: str
) -> Path:
  (device, arch) = get_device_and_arch(fpga_part)
  return ARCH_SUMMARY_DIR / f"{arch.name}.json"

def get_arch_summary(
  fpga_part: str
) -> ArchSummary:
  (device, arch) = get_device_and_arch(fpga_part)

  global _arch_summaries
  if arch not in _arch_summaries:
    summary_path = get_arch_summary_path(fpga_part)
    _arch_summaries[arch] = ArchSummary(helpers.read_json(summary_path))

  return _arch_summaries[arch]

def get_webpack_parts() -> set[str]:
  load_part_files()
  global _parts_webpack_db
  return set(_parts_webpack_db.keys())

def get_all_parts() -> set[str]:
  load_part_files()
  global _parts_all_db
  return set(_parts_all_db.keys())
