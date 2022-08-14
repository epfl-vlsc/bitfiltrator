# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
from pathlib import Path

import helpers
import resources
from bit_locator import BitLocator
from bitstream import Bitstream
from device_summary import DeviceSummary
from fpga_resources import Bram, Lut
from frame import ConfigFrame, FrameAddressRegister


def extract_frames(
  bitstream: Bitstream,
  dev_summary: DeviceSummary
) -> dict[
  tuple[
    str, # SLR name
    FrameAddressRegister # FAR
  ],
  ConfigFrame
]:
  slrNameFar_frame_dict: dict[tuple[str, FrameAddressRegister], ConfigFrame] = dict()

  for (idcode, far_dict) in bitstream.get_per_far_configuration_arrays().items():
    slrName = dev_summary.get_slr_name(idcode)
    for (far, config_frames) in far_dict.items():
      assert len(config_frames) == 1, f"Error: Found multiple writes to FAR 0x{far.to_hex()}!"
      frame = config_frames[0]
      slrNameFar_frame_dict[(slrName, far)] = frame

  return slrNameFar_frame_dict

def reconstruct_lut_init_hex(
  slrNameFar_frame_dict: dict[tuple[str, FrameAddressRegister], ConfigFrame], # Frame contents
  slr_name: str, # Target SLR name
  fars: list[FrameAddressRegister], # Target frame addresses (one per LUT bit)
  frame_ofsts: list[int] # Frame offset (in bits, one per LUT bit)
) -> str:
  lut = Lut()

  for (idx, (far, frame_ofst)) in enumerate(zip(fars, frame_ofsts)):
    key = (slr_name, far)
    frame = slrNameFar_frame_dict[key]
    bit_value = frame.bit(frame_ofst)
    lut.set_bit(idx, bit_value)

  return lut.to_hex()

def concatenate_bram_initialization(
  key_val: dict[str, str]
) -> str:
  def key_to_int(key: str) -> int:
    # The key is of the form r"INIT_[0-9a-fA-F]+". We sort according to the
    # integer value of the hex suffix.
    pattern = r"INITP?_(?P<hex>[0-9a-fA-F]+)"
    match = helpers.regex_match(pattern, key)
    value_hex = match.group("hex")
    value_int = int(value_hex, 16)
    return value_int

  # UG-573: INIT_00 is bit 255:0, INIT_3F is bit 16383:16128.
  # We want the MSb on the left and the LSb on the right, so we must reverse the
  # keys before concatenating their string representation.
  sorted_keys = sorted(key_val.keys(), key=key_to_int, reverse=True)
  sorted_values = [helpers.verilog_num_to_hex(key_val[key]) for key in sorted_keys]
  concatenated = "".join(sorted_values)
  return concatenated

def reconstruct_bram_mem_initialization(
  slrNameFar_frame_dict: dict[tuple[str, FrameAddressRegister], ConfigFrame], # Frame contents
  slr_name: str, # Target SLR name
  fars: list[FrameAddressRegister], # Target frame addresses (one per BRAM content bit)
  frame_ofsts: list[int] # Frame offset (in bits, one per BRAM content bit)
) -> str:
  bram = Bram()

  for (idx, (far, frame_ofst)) in enumerate(zip(fars, frame_ofsts)):
    key = (slr_name, far)
    frame = slrNameFar_frame_dict[key]
    bit_value = frame.bit(frame_ofst)
    bram.set_mem_bit(idx, bit_value)

  return bram.mem_to_hex()

def reconstruct_bram_parity_initialization(
  slrNameFar_frame_dict: dict[tuple[str, FrameAddressRegister], ConfigFrame], # Frame contents
  slr_name: str, # Target SLR name
  fars: list[FrameAddressRegister], # Target frame addresses (one per BRAM content bit)
  frame_ofsts: list[int] # Frame offset (in bits, one per BRAM content bit)
) -> str:
  bram = Bram()

  for (idx, (far, frame_ofst)) in enumerate(zip(fars, frame_ofsts)):
    key = (slr_name, far)
    frame = slrNameFar_frame_dict[key]
    bit_value = frame.bit(frame_ofst)
    bram.set_parity_bit(idx, bit_value)

  return bram.parity_to_hex()

def check_state(
  bitstream_path: str | Path,
  expected_values_json_path: str | Path
) -> bool:

  bitstream = Bitstream.from_file_path(bitstream_path)
  assert not bitstream.is_partial(), f"Error: {bitstream} is a partial bitstream!"

  bitlocator = BitLocator(bitstream.header.fpga_part)
  dev_summary = resources.get_device_summary(bitstream.header.fpga_part)

  slrNameFar_frame_dict = extract_frames(bitstream, dev_summary)
  expected_values = helpers.read_json(expected_values_json_path)

  ############

  print(f"[{bitstream.header.fpga_part}] Checking LUTs")
  for (lut_name, lut_properties) in expected_values["luts"].items():
    lut_loc = lut_properties["loc"]
    (slr_name, fars, frame_ofsts) = bitlocator.locate_lut(lut_loc)

    expected_lut_init = helpers.verilog_num_to_hex(lut_properties["INIT"])
    found_lut_init = reconstruct_lut_init_hex(slrNameFar_frame_dict, slr_name, fars, frame_ofsts)

    if found_lut_init != expected_lut_init:
      print(f"[{bitstream.header.fpga_part}] Error: LUT init incorrect for {lut_loc}\nReceived: {found_lut_init}\nExpected:{expected_lut_init}")
      return False
    # else:
    #   print(f"{lut_loc} matches 64'h{expected_lut_init}")
  print(f"[{bitstream.header.fpga_part}] All LUTs are correct")

  ############

  print(f"[{bitstream.header.fpga_part}] Checking FFs")
  for (reg_name, reg_properties) in expected_values["regs"].items():
    reg_loc = reg_properties["loc"]
    (slr_name, far, frame_ofst) = bitlocator.locate_reg(reg_loc)

    key = (slr_name, far)
    frame = slrNameFar_frame_dict[key]

    # "XAPP1230: Configuration readback capture (v1.1, November 20, 2015)", pg 20
    #
    #   All of the CLB registers have an inversion when performing a readback capture. The CLB
    #   registers are inverted when captured, so a 0 should be seen in the readback capture file as a 1.
    #   This does not exist for UltraScale FPGA block RAM, distributed RAM, or SRL captures.
    #
    # This is why I invert the INIT value before using it as the expected register value
    # in the frame.
    expected_reg_init = helpers.verilog_num_to_int(reg_properties["INIT"])
    expected_reg_init = 0 if expected_reg_init == 1 else 1
    found_reg_init = frame.bit(frame_ofst)

    if found_reg_init != expected_reg_init:
      print(f"[{bitstream.header.fpga_part}] Error: FF init incorrect for {reg_loc}\nReceived: {found_reg_init}\nExpected:{expected_reg_init}")
      return False
    # else:
    #   print(f"{reg_loc} matches 1'b{expected_reg_init}")
  print(f"[{bitstream.header.fpga_part}] All FFs are correct")

  ############

  print(f"[{bitstream.header.fpga_part}] Checking BRAMs")
  for (bram_name, bram_properties) in expected_values["brams"].items():
    bram_loc = bram_properties["loc"]
    (slr_name, mem_fars, mem_frame_ofsts, parity_fars, parity_frame_ofsts) = bitlocator.locate_bram(bram_loc)
    expected_mem_init = concatenate_bram_initialization(bram_properties["memory"])
    expected_parity_init = concatenate_bram_initialization(bram_properties["parity"])
    found_mem_init = reconstruct_bram_mem_initialization(slrNameFar_frame_dict, slr_name, mem_fars, mem_frame_ofsts)
    found_parity_init = reconstruct_bram_parity_initialization(slrNameFar_frame_dict, slr_name, parity_fars, parity_frame_ofsts)

    if found_mem_init != expected_mem_init:
      print(f"[{bitstream.header.fpga_part}] Error: BRAM mem init incorrect for {bram_loc}\nReceived: {found_mem_init}\nExpected:{expected_mem_init}")
      return False
    # else:
    #   print(f"BRAM mem at {bram_loc} ok.")

    if found_parity_init != expected_parity_init:
      print(f"[{bitstream.header.fpga_part}] Error: BRAM mem parity incorrect for {bram_loc}\nReceived: {found_parity_init}\nExpected: {expected_parity_init}")
      return False
    # else:
    #   print(f"BRAM parity at {bram_loc} ok.")
  print(f"[{bitstream.header.fpga_part}] All BRAMs are correct")

  # Everything must have been correct if we reached this point.
  return True

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Experiments.")
  parser.add_argument("bitstream", type=str, help="Input bitstream (with header).")
  parser.add_argument("expected_values_json", type=str, help="Input JSON file containing expected LUT/FF/BRAM values.")
  args = parser.parse_args()

  check_state(args.bitstream, args.expected_values_json)

  print("Done")
