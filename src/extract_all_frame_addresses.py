# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
from collections import defaultdict
from pathlib import Path

import packet as pkt
import packet_spec as pkt_spec
from arch_spec import ArchSpec
from bitstream import Bitstream
from frame import FrameAddressRegister
from frame_spec import FarBlockType


def extract_all_frame_addresses(
  bitstream_path: str | Path,
  out_fars_csv: str | Path
) -> None:
  bitstream = Bitstream.from_file_path(bitstream_path)
  assert not bitstream.is_partial(), f"Error: {bitstream_path} is a partial bitstream. Need a full bitstream to extract all frame addresses."
  assert bitstream.is_per_frame_crc(), f"Error: {bitstream_path} is not a bitstream with per-frame CRCs. Need per-frame CRCs to extract all frame addresses."

  ar_spec = ArchSpec.create_spec(bitstream.header.fpga_part)

  # Extract all FARs from bitstream.
  idcode_fars_dict: dict[int, list[FrameAddressRegister]] = defaultdict(list)
  current_idcode: int = None
  for packet in bitstream._packets:
    if pkt.is_reg_write_pkt(packet, pkt_spec.Register.IDCODE):
      current_idcode = packet.data[0]
    elif pkt.is_reg_write_pkt(packet, pkt_spec.Register.FAR):
      # There will be a few dummy writes to FAR before the IDCODE is known. We can safely skip these.
      if current_idcode is not None:
        current_far = FrameAddressRegister.from_int(packet.data[0], ar_spec)
        # Some writes to FAR at the end of each SLR's configuration (after the last configuration frame
        # of the SLR is written) are to a reserved address. We ignore these as they do not correspond
        # to valid frame addresses.
        far_is_valid = (current_far.block_type == FarBlockType.CLB_IO_CLK) or (current_far.block_type == FarBlockType.BRAM_CONTENT)
        if far_is_valid:
          idcode_fars_dict[current_idcode].append(current_far)

  # Eliminate duplicate FARs (will happen in multi-SLR devices) and sort to have all FARs in order.
  for idcode in idcode_fars_dict:
    fars = idcode_fars_dict[idcode]
    # We convert the FARs to ints before removing duplicates as FARs themselves are not hashable.
    fars_int = [far.to_int() for far in fars]
    uniq_fars_int = set(fars_int)
    uniq_sorted_fars_int = sorted(list(uniq_fars_int))
    idcode_fars_dict[idcode] = [FrameAddressRegister.from_int(far_int, ar_spec) for far_int in uniq_sorted_fars_int]

  # Emit output file.
  dump_fars(idcode_fars_dict, out_fars_csv)

def dump_fars(
  idcode_fars: dict[int, list[FrameAddressRegister]],
  filename_out: str
) -> None:
  lines: list[str] = list()

  csv_hdr = f"IDCODE,FAR,RESERVED,BLOCK_TYPE,ROW_ADDR,COL_ADDR,MINOR_ADDR"
  lines.append(csv_hdr)
  for (idcode, fars) in idcode_fars.items():
    for far in fars:
      lines.append(f"0x{idcode:0>8x},0x{far.to_hex()},{far.reserved},{far.block_type.name},{far.row_addr},{far.col_addr},{far.minor_addr}")

  with open(filename_out, "w") as f:
    f.write("\n".join(lines))

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Extracts all frame addresses from a debug bitstream.")
  parser.add_argument("bitstream", type=str, help="Input bitstream (with header). Must be a full debug bitstream (c.f. UG908 table 41).")
  parser.add_argument("out_fars_csv", type=str, help="Output CSV file containing all FARs.")
  args = parser.parse_args()

  extract_all_frame_addresses(args.bitstream, args.out_fars_csv)

  print("Done")
