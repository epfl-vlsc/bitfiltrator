# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
from pathlib import Path

from bitstream import Bitstream


def parse_bitstream(
  bitstream: str | Path,
  out: str | Path
) -> None:
  bitstream = Bitstream.from_file_path(bitstream)

  # Write output dump file.
  with open(out, "w") as f:
    lines: list[str] = list()

    lines.append(f"part = {bitstream.header.fpga_part}")
    lines.append(f"is_crc = {bitstream.is_crc_enabled()}")
    lines.append(f"is_encrypt = {bitstream.is_encrypted()}")
    lines.append(f"is_compress = {bitstream.is_compressed()}")
    lines.append(f"is_per_frame_crc = {bitstream.is_per_frame_crc()}")
    lines.append(f"is_partial = {bitstream.is_partial()}")
    lines.append("")
    for packet in bitstream.packets:
      lines.append(str(packet))

    f.write("\n".join(lines))

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Parses xilinx .bit files.")
  parser.add_argument("bitstream", type=str, help="Input bitstream (with header).")
  parser.add_argument("out", type=str, help="Output bitstream dump.")
  args = parser.parse_args()

  parse_bitstream(args.bitstream, args.out)

  print("Done")
