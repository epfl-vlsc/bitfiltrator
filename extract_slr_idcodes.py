# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
from pathlib import Path

import format_json
import helpers
import packet as pkt
import packet_spec as pkt_spec
from bitstream import Bitstream


def extract_slr_idcodes(
  bitstream_path: str | Path,
  device_info_json_path: str | Path,
  out_json_path: str | Path
) -> None:
  bitstream = Bitstream.from_file_path(bitstream_path)
  assert not bitstream.is_partial(), f"Error: Bitstream is a partial bitstream. Expected to receive a full bitstream."

  # The IDCODEs in the bitstream are returned in the same order in which the SLRs are configured.
  idcodes: list[str] = list()
  for packet in bitstream._packets:
    if pkt.is_reg_write_pkt(packet, pkt_spec.Register.IDCODE):
      idcode_int = packet.data[0]
      idcode_str = f"0x{idcode_int:0>8x}"
      idcodes.append(idcode_str)

  device_info = helpers.read_json(device_info_json_path)
  slr_configOrderIdx = {
    slrName: slrProperties["config_order_idx"]
    for (slrName, slrProperties) in device_info["composition"]["slrs"].items()
  }

  num_idcodes = len(idcodes)
  num_slrs = len(slr_configOrderIdx)
  assert num_idcodes == num_slrs, f"Error: Expected number of writes to IDCODE register in bitstream ({num_idcodes}) to match number of SLRs ({num_slrs})."

  # Sort the SLR names by their CONFIG_ORDER_INDEX property.
  slrName_configOrdered = [
    slrName
    for (slrName, configOrderIdx) in
    sorted(slr_configOrderIdx.items(), key=lambda tup: tup[1])
  ]

  slrName_idcode = dict(zip(slrName_configOrdered, idcodes))
  with open(out_json_path, "w") as f:
    json_str = format_json.emit(slrName_idcode, sort_keys=True)
    f.write(json_str)

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Extracts writes to the IDCODE register in a bitstream (in order).")
  parser.add_argument("bitstream", type=str, help="Input bitstream (with header). Must be a full bitstream.")
  parser.add_argument("device_info_json", type=str, help="Input JSON file containing device information.")
  parser.add_argument("out_json", type=str, help="Output JSON file containing IDCODEs.")
  args = parser.parse_args()

  extract_slr_idcodes(args.bitstream, args.device_info_json, args.out_json)

  print("Done")
