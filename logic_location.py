# author: Sahand Kashani <sahand.kashani@epfl.ch>

import math
import re

import helpers


class LogicLocationFile:
  def __init__(
    self,
    ll_path: str
  ) -> None:
    with open(ll_path, "r") as f:
      all_lines = f.readlines()

    # We only keep lines containing bit information (lines that start with the "Bit" string).
    self.bit_locs = [BitLoc.create_bitloc(line) for line in all_lines if line.startswith("Bit")]

class BitLoc:
  def __init__(
    self,
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    block_x: int,
    block_y: int
  ) -> None:
    self.ofst = ofst
    self.frame_addr = frame_addr
    self.frame_ofst = frame_ofst
    self.slr_name = slr_name
    self.slr_number = slr_number
    self.block = block
    self.block_x = block_x
    self.block_y = block_y

  def __str__(self) -> str:
    return f"{self.slr_name}, {self.block}, FAR = 0x{self.frame_addr:0>32x}, FRAME_OFST = {self.frame_ofst}"

  # Factory method to create a bit logic location.
  #
  # Don't know how to add circular type hint to THIS class, so I omit return type.
  # Returns either {RegLoc, LutramLoc, BramRegLoc, BramMemParityLoc, BramMemLoc}, or None if the
  # bit line does not correspond to any known bit line.
  @staticmethod
  def create_bitloc(
    bit_line: str
  ):
    # We only keep lines containing bit information. The format of "bit" lines is:
    #
    #   <offset> <frame address> <frame offset> <SLR name> <SLR number> <information>
    #   Bit   10585636 0x0000670c    4 SLR0 1 Block=SLICE_X53Y0 Latch=BQ Net=FDRE_gen[49].FDRE_inst_n_0
    #
    # The frame address is in hex, hence why I don't simply use \d+ to parse it.
    # Note that the "-" in <ofst_dec> is simply because I generate a dummy logic
    # location file to reverse-engineer LUT encodings and I want explicitly mark
    # the file with "-1" as the bit offset to easily know it is an unofficial output.
    pattern = r"Bit\s+(?P<ofst_dec>-?\d+)\s+0x(?P<frame_addr_hex>[0-9a-fA-F]+)\s+(?P<frame_ofst_dec>\d+)\s+(?P<slr_name>\w+)\s+(?P<slr_number>\d+)\s+(?P<info>.*)"
    match = re.match(pattern, bit_line)
    assert match is not None, f"Error: Unrecognized bit line {bit_line} in logic location file."

    ofst = int(match.group("ofst_dec"))
    frame_addr = int(match.group("frame_addr_hex"), 16)
    frame_ofst = int(match.group("frame_ofst_dec"))
    slr_name = match.group("slr_name")
    slr_number = int(match.group("slr_number"))

    # Different bit formats exist depending on the type of resource that is being documented:
    #
    # FDRE:
    #   Bit   10585634 0x0000670c    2 SLR0 1 Block=SLICE_X53Y0 Latch=AQ Net=FDRE_gen[49].FDRE_inst_n_0
    #
    # LUTRAM:
    #   Bit   23341243 0x0000e403  475 SLR1 0 Block=SLICE_X118Y249 Ram=F:16
    #
    # LUT (this is a custom format emitted by lut_init_sweep_to_logic_loc.py, not by Vivado):
    #   Bit         -1 0x00005382 868 SLR0 0 Block=SLICE_X0Y13 Lut=E:46
    #
    # BRAM:
    #   Bit    4428319 0x00001583  319 SLR0 0 Block=RAMB36_X2Y0 Latch=DOBU15 Net=tmp[3][63]
    #   Bit  103815936 0x00800100    0 SLR0 0 Block=RAMB36_X2Y0 RAM=B:BIT0
    #   Bit  103816189 0x00800100  253 SLR0 0 Block=RAMB36_X2Y0 RAM=B:PARBIT15

    # The info group is a series of key=value pairs separated by whitespace.
    info_pairs: list[str] = match.group("info").split()
    info_dict: dict[str, str] = dict()
    for k_equal_v in info_pairs:
      (k, v) = k_equal_v.split("=")
      info_dict[k] = v

    # All bit lines have a "Block" key in the info region, so it is ok to index
    # this name directly.
    block = info_dict["Block"]
    block_pattern = r"^.*_X(?P<x>\d+)Y(?P<y>\d+)$"
    block_match = helpers.regex_match(block_pattern, block)
    block_x = int(block_match.group("x"))
    block_y = int(block_match.group("y"))

    is_slice = block.startswith("SLICE")
    is_bram = block.startswith("RAMB")
    assert is_slice or is_bram, f"Error: Unknown location \"{bit_line}\""

    if is_slice:
      return SliceLoc.from_loc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, block_x, block_y, info_dict)
    else:
      return BramLoc.from_loc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, block_x, block_y, info_dict)

class SliceLoc(BitLoc):
  def __init__(
    self,
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    block_x: int,
    block_y: int
  ) -> None:
    super().__init__(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, block_x, block_y)

  def __str__(self) -> str:
    return super().__str__()

  @staticmethod
  def from_loc(
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    block_x: int,
    block_y: int,
    info: dict[str, str]
  ):
    is_reg = "Net" in info
    is_mem = ("Ram" in info) or ("Rom" in info)
    is_lut = "Lut" in info
    assert is_reg or is_mem or is_lut, f"Error: Slice element is not a register, LUTRAM, or LUT"

    if is_reg:
      return RegLoc.from_loc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, block_x, block_y, info)
    elif is_mem:
      return LutramLoc.from_loc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, block_x, block_y, info)
    else:
      return LutLoc.from_loc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, block_x, block_y, info)

# Bit   10585634 0x0000670c    2 SLR0 1 Block=SLICE_X53Y0 Latch=AQ Net=FDRE_gen[49].FDRE_inst_n_0
class RegLoc(SliceLoc):
  def __init__(
    self,
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    block_x: int,
    block_y: int,
    reg: str,
    net: str
  ) -> None:
    super().__init__(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, block_x, block_y)
    self.reg = reg
    self.net = net

  def __str__(self) -> str:
    return f"{super().__str__()}, REG = {self.reg}"

  @staticmethod
  def from_loc(
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    block_x: int,
    block_y: int,
    info: dict[str, str]
  ):
    latch = info["Latch"]
    latch_pattern = r"^(?P<letter>[A-H])Q(?P<number>2?)$"
    latch_match = helpers.regex_match(latch_pattern, latch)
    # Vivado reprsents register names as "<letter>FF<num>", so I add "FF" in the middle here.
    reg = f"{latch_match.group('letter')}FF{latch_match.group('number')}"
    net = info["Net"]
    return RegLoc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, block_x, block_y, reg, net)

# Bit   23341243 0x0000e403  475 SLR1 0 Block=SLICE_X118Y249 Ram=F:16
class LutramLoc(SliceLoc):
  def __init__(
    self,
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    block_x: int,
    block_y: int,
    mem_id: str,
    mem_bit: int
  ) -> None:
    super().__init__(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, block_x, block_y)
    self.mem_id = mem_id
    self.mem_bit = mem_bit

  def __str__(self) -> str:
    return f"{super().__str__()}, MEM_ID = {self.mem_id}, MEM_BIT = {self.mem_bit}"

  @staticmethod
  def from_loc(
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    block_x: int,
    block_y: int,
    info: dict[str, str]
  ):
    mem = info["Ram"] if "Ram" in info else info["Rom"]
    mem_pattern = r"(?P<letter>[A-H]):(?P<bit>\d+)"
    mem_match = helpers.regex_match(mem_pattern, mem)
    mem_id = mem_match.group("letter")
    mem_bit = int(mem_match.group("bit"))
    return LutramLoc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, block_x, block_y, mem_id, mem_bit)

class LutLoc(SliceLoc):
  def __init__(
    self,
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    block_x: int,
    block_y: int,
    mem_id: str,
    mem_bit: int
  ) -> None:
    super().__init__(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, block_x, block_y)
    self.mem_id = mem_id
    self.mem_bit = mem_bit

  def __str__(self) -> str:
    return f"{super().__str__()}, MEM_ID = {self.mem_id}, MEM_BIT = {self.mem_bit}"

  @staticmethod
  def from_loc(
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    block_x: int,
    block_y: int,
    info: dict[str, str]
  ):
    mem = info["Lut"]
    mem_pattern = r"(?P<letter>[A-H]):(?P<bit>\d+)"
    mem_match = helpers.regex_match(mem_pattern, mem)
    mem_id = mem_match.group("letter")
    mem_bit = int(mem_match.group("bit"))
    return LutLoc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, block_x, block_y, mem_id, mem_bit)

class BramLoc(BitLoc):
  def __init__(
    self,
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    bram_mem_size_kb: int,
    bram_parity_size_kb: int,
    block_x: int,
    block_y: int
  ) -> None:
    super().__init__(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, block_x, block_y)
    self.bram_mem_size_kb = bram_mem_size_kb
    self.bram_parity_size_kb = bram_parity_size_kb

  def __str__(self) -> str:
    return super().__str__()

  @staticmethod
  def from_loc(
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    block_x: int,
    block_y: int,
    info: dict[str, str]
  ):
    def previous_power_of_2(x: int) -> int:
      return 1 << int(math.log2(x))

    block_pattern = r"^RAMB(?P<size_kb>\d+)_X(?P<x>\d+)Y(?P<y>\d+)$"
    block_match = helpers.regex_match(block_pattern, block)
    bram_size_kb = int(block_match.group("size_kb"))

    previous_power_of_2_kb = previous_power_of_2(bram_size_kb)
    bram_mem_size_kb = previous_power_of_2_kb
    bram_parity_size_kb = bram_size_kb - bram_mem_size_kb

    is_bram_reg = ("Latch" in info) and ("Net" in info)
    is_bram_ram = "RAM" in info
    assert is_bram_reg or is_bram_ram, f"Error: BRAM element is not a BRAM register or a BRAM RAM"

    if is_bram_reg:
      return BramRegLoc.from_loc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, bram_mem_size_kb, bram_parity_size_kb, block_x, block_y, info)
    else:
      ram = info["RAM"]
      is_parity = "PARBIT" in ram
      is_memory = "BIT" in ram
      assert is_parity or is_memory, f"Error: BRAM RAM is not a parity or memory element"

      if is_parity:
        return BramMemParityLoc.from_loc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, bram_mem_size_kb, bram_parity_size_kb, block_x, block_y, info)
      else:
        return BramMemLoc.from_loc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, bram_mem_size_kb, bram_parity_size_kb, block_x, block_y, info)

#   Bit    4428319 0x00001583  319 SLR0 0 Block=RAMB36_X2Y0 Latch=DOBU15 Net=tmp[3][63]
class BramRegLoc(BramLoc):
  def __init__(
    self,
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    bram_mem_size_kb: int,
    bram_parity_size_kb: int,
    block_x: int,
    block_y: int,
    reg: str,
    net: str
  ) -> None:
    super().__init__(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, bram_mem_size_kb, bram_parity_size_kb, block_x, block_y)
    self.reg = reg
    self.net = net

  def __str__(self) -> str:
    return f"{super().__str__()}, REG = {self.reg}"

  @staticmethod
  def from_loc(
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    bram_mem_size_kb: int,
    bram_parity_size_kb: int,
    block_x: int,
    block_y: int,
    info: dict[str, str]
  ):
    reg = info["Latch"]
    net = info["Net"]
    return BramRegLoc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, bram_mem_size_kb, bram_parity_size_kb, block_x, block_y, reg, net)

#   Bit  103815936 0x00800100    0 SLR0 0 Block=RAMB36_X2Y0 RAM=B:BIT0
class BramMemLoc(BramLoc):
  def __init__(
    self,
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    bram_mem_size_kb: int,
    bram_parity_size_kb: int,
    block_x: int,
    block_y: int,
    mem_bit: int
  ) -> None:
    super().__init__(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, bram_mem_size_kb, bram_parity_size_kb, block_x, block_y)
    self.mem_bit = mem_bit

  def __str__(self) -> str:
    return f"{super().__str__()}"

  @staticmethod
  def from_loc(
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    bram_mem_size_kb: int,
    bram_parity_size_kb: int,
    block_x: int,
    block_y: int,
    info: dict[str, str]
  ):
    mem = info["RAM"]
    mem_pattern = r"^B:BIT(?P<bit>\d+)$"
    mem_match = helpers.regex_match(mem_pattern, mem)
    mem_bit = int(mem_match.group("bit"))
    return BramMemLoc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, bram_mem_size_kb, bram_parity_size_kb, block_x, block_y, mem_bit)

#   Bit  103816189 0x00800100  253 SLR0 0 Block=RAMB36_X2Y0 RAM=B:PARBIT15
class BramMemParityLoc(BramLoc):
  def __init__(
    self,
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    bram_mem_size_kb: int,
    bram_parity_size_kb: int,
    block_x: int,
    block_y: int,
    par_bit: int
  ) -> None:
    super().__init__(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, bram_mem_size_kb, bram_parity_size_kb, block_x, block_y)
    self.par_bit = par_bit

  def __str__(self) -> str:
    return f"{super().__str__()}, PAR_BIT = {self.par_bit}"

  @staticmethod
  def from_loc(
    ofst: int,
    frame_addr: int,
    frame_ofst: int,
    slr_name: str,
    slr_number: int,
    block: str,
    bram_mem_size_kb: int,
    bram_parity_size_kb: int,
    block_x: int,
    block_y: int,
    info: dict[str, str]
  ):
    mem = info["RAM"]
    mem_pattern = r"^B:PARBIT(?P<bit>\d+)$"
    mem_match = helpers.regex_match(mem_pattern, mem)
    par_bit = int(mem_match.group("bit"))
    return BramMemParityLoc(ofst, frame_addr, frame_ofst, slr_name, slr_number, block, bram_mem_size_kb, bram_parity_size_kb, block_x, block_y, par_bit)
