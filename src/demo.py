import argparse
from pathlib import Path

from bit_locator import BitLocator
from bitstream import Bitstream

def print_lut_info(
  bitlocator: BitLocator,
  lut: str
) -> None:
  (slr_name, frame_addrs, frame_ofsts) = bitlocator.locate_lut(lut)
  print(f"{lut}")
  for (init_idx, (frame_addr, frame_ofst)) in enumerate(zip(frame_addrs, frame_ofsts)):
    print(f"INIT[{init_idx:>2d}] -> {slr_name}, frame address: 0x{frame_addr.to_hex()} ({frame_addr}), frame offset: {frame_ofst:>4d}")

def print_ff_info(
  bitlocator: BitLocator,
  ff: str
) -> None:
  (slr_name, frame_addr, frame_ofst) = bitlocator.locate_reg(ff)
  print(f"{ff}")
  print(f"INIT -> {slr_name}, frame address: 0x{frame_addr.to_hex()} ({frame_addr}), frame offset: {frame_ofst:>4d}")

def print_bram_info(
  bitlocator: BitLocator,
  bram: str
) -> None:
  (slr_name, content_frame_addrs, content_frame_ofsts, parity_frame_addrs, parity_frame_ofsts) = bitlocator.locate_bram(bram)
  print(f"{bram}")
  for (init_idx, (frame_addr, frame_ofst)) in enumerate(zip(content_frame_addrs, content_frame_ofsts)):
    print(f"INIT[{init_idx:>5d}] -> {slr_name}, frame address: 0x{frame_addr.to_hex()} ({frame_addr}), frame offset: {frame_ofst:>4d}")
  for (init_idx, (frame_addr, frame_ofst)) in enumerate(zip(parity_frame_addrs, parity_frame_ofsts)):
    print(f"INIT_P[{init_idx:>5d}] -> {slr_name}, frame address: 0x{frame_addr.to_hex()} ({frame_addr}), frame offset: {frame_ofst:>4d}")


# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Demo application that locates a resource and prints its SLR name, frame addresses, and frame offsets.")
  parser.add_argument("bitstream", type=str, help="Input bitstream (with header). Must be a full bitstream, not a partial one.")
  parser.add_argument("--luts", type=str, nargs="*", help="Name of LUTs to locate in the form of SLICE_X(\d+)Y(\d+)/[A-H]6LUT")
  parser.add_argument("--ffs", type=str, nargs="*", help="Name of Flip-Flops to locate in the form of SLICE_X(\d+)Y(\d+)/[A-H]FF2?")
  parser.add_argument("--brams", type=str, nargs="*", help="Name of 18K BRAMs to locate in the form of RAMB18_X(\d+)Y(\d+)")
  args = parser.parse_args()

  bitstream = Bitstream.from_file_path(Path(args.bitstream))
  assert not bitstream.is_partial(), f"Error: {bitstream} is a partial bitstream!"

  bitlocator = BitLocator(bitstream.header.fpga_part)

  for lut in args.luts:
    print_lut_info(bitlocator, lut)
    print()

  for ff in args.ffs:
    print_ff_info(bitlocator, ff)
    print()

  for bram in args.brams:
    print_bram_info(bitlocator, bram)
    print()