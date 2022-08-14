# author: Sahand Kashani <sahand.kashani@epfl.ch>

from collections import defaultdict

import numpy as np

import bitstream_spec as bit_spec
import helpers
import resources
from arch_spec import ArchSpec
from frame_spec import FarBlockType


class FrameAddressRegister:
  def __init__(
    self,
    reserved: int,
    block_type: FarBlockType,
    row_addr: int,
    col_addr: int,
    minor_addr: int,
    spec: ArchSpec
  ) -> None:
    self.spec = spec
    self.reserved = reserved
    self.block_type = block_type
    self.row_addr = row_addr
    self.col_addr = col_addr
    self.minor_addr = minor_addr

  def to_bin(self) -> str:
    # Compute binary representation of every field with their actual bitwidth.
    # Python's f-strings allow using a custom width in the format.
    b_reserved = f"{self.reserved:0>{self.spec.far_reserved_width()}b}"
    b_block_type = f"{self.block_type.value:0>{self.spec.far_block_type_width()}b}"
    b_row_addr = f"{self.row_addr:0>{self.spec.far_row_address_width()}b}"
    b_col_addr = f"{self.col_addr:0>{self.spec.far_column_address_width()}b}"
    b_minor_addr = f"{self.minor_addr:0>{self.spec.far_minor_address_width()}b}"

    b_far = f"{b_reserved}{b_block_type}{b_row_addr}{b_col_addr}{b_minor_addr}"
    return b_far

  def to_hex(self) -> str:
    b_far = self.to_bin()
    h_far = f"{int(b_far, 2):0>8x}"
    return h_far

  def to_int(self) -> int:
    b_far = self.to_bin()
    i_far = int(b_far, 2)
    return i_far

  def __hash__(self) -> int:
    return hash((
      self.__class__,
      self.spec,
      self.reserved,
      self.block_type,
      self.row_addr,
      self.col_addr,
      self.minor_addr
    ))

  def __eq__(self, other) -> bool:
    self_keys = (self.reserved, self.block_type, self.row_addr, self.col_addr, self.minor_addr)
    other_keys = (other.reserved, other.block_type, other.row_addr, other.col_addr, other.minor_addr)
    return self_keys == other_keys

  @staticmethod
  def from_int(
    far: int,
    spec: ArchSpec
  ):
    # Sanity-check to ensure that FAR is an int as some types like numpy int64 look like it, but create
    # problems for serialization to JSON in other places in the code.
    far = int(far)
    reserved = helpers.bits(far, spec.far_reserved_idx_high(), spec.far_reserved_idx_low())
    block_type = FarBlockType(helpers.bits(far, spec.far_block_type_idx_high(), spec.far_block_type_idx_low()))
    row_addr = helpers.bits(far, spec.far_row_address_idx_high(), spec.far_row_address_idx_low())
    col_addr = helpers.bits(far, spec.far_column_address_idx_high(), spec.far_column_address_idx_low())
    minor_addr = helpers.bits(far, spec.far_minor_address_idx_high(), spec.far_minor_address_idx_low())
    return FrameAddressRegister(reserved, block_type, row_addr, col_addr, minor_addr, spec)

  def __str__(self) -> str:
    return f"BLOCK_TYPE = {self.block_type.name}, ROW_ADDR = {self.row_addr:>3d}, COL_ADDR = {self.col_addr:>3d}, MINOR_ADDR = {self.minor_addr:>3d}"

class FrameAddressIncrementer:
  def __init__(
    self,
    fpga_part: str
  ) -> None:
    device_summary = resources.get_device_summary(fpga_part)

    # I want a dict like:
    #
    #   {
    #     <idcode>: {
    #       <rowMajors>: [ <numbers> ] // num minors per col major
    #     }
    #   }
    self.num_minors_per_std_colMajor: dict[
      int, # IDCODE
      dict[
        int, # row major
        list[int] # num minors per column
      ]
    ] = defaultdict(
      lambda: defaultdict(list)
    )

    self.num_minors_per_bram_colMajor: dict[
      int, # IDCODE
      dict[
        int, # row major
        list[int] # num minors per column
      ]
    ] = defaultdict(
      lambda: defaultdict(list)
    )

    for slrName in device_summary.get_slr_names():
      idcode = device_summary.get_slr_idcode(slrName)
      # Some devices have more "FAR" rows that the "clock region" rows they expose
      # in vivado. It is important to use the "FAR" row as the upper bound as it
      # is the real number of frames in the bitstream.
      min_rowMajor = device_summary.get_min_far_row_idx(slrName)
      max_rowMajor = device_summary.get_max_far_row_idx(slrName)
      for rowMajor in range(min_rowMajor, max_rowMajor + 1):
        self.num_minors_per_std_colMajor[idcode][rowMajor] = device_summary.get_num_minors_per_std_col_major(slrName, rowMajor)
        self.num_minors_per_bram_colMajor[idcode][rowMajor] = device_summary.get_num_minors_per_bram_content_col_major(slrName, rowMajor)

  def get_colMajors_numMinors_count(
    self,
    idcode: int,
    far: FrameAddressRegister
  ) -> tuple[
    int, # num col majors
    int  # num minors in col major
  ]:
    if far.block_type == FarBlockType.CLB_IO_CLK:
      num_col_majors = len(self.num_minors_per_std_colMajor[idcode][far.row_addr])
      num_minors_in_col_major = self.num_minors_per_std_colMajor[idcode][far.row_addr][far.col_addr]
    elif far.block_type == FarBlockType.BRAM_CONTENT:
      num_col_majors = len(self.num_minors_per_bram_colMajor[idcode][far.row_addr])
      num_minors_in_col_major = self.num_minors_per_bram_colMajor[idcode][far.row_addr][far.col_addr]
    else:
      assert False, f"Error: Unexpected FAR block type {far.block_type}"

    return (num_col_majors, num_minors_in_col_major)

  # Increments the FAR by 1, wrapping back to 0 if the last FAR is reached.
  # Returns the incremented FAR.
  def increment(
    self,
    idcode: int,
    far: FrameAddressRegister
  ) -> FrameAddressRegister:
    # Increment minor first, then col major, row major, and block type.
    # The reserved field is always kept unchanged.

    # # Debug.
    # print(f"0x{idcode:0>8x},0x{far.to_hex()},{far.reserved},{far.block_type.name},{far.row_addr},{far.col_addr},{far.minor_addr}")

    (num_col_majors, num_minors_in_col_major) = self.get_colMajors_numMinors_count(idcode, far)

    new_minor_addr = far.minor_addr
    new_col_addr = far.col_addr
    new_row_addr = far.row_addr
    new_block_type = far.block_type

    new_minor_addr += 1

    # Carry over minor to col major.
    if new_minor_addr == num_minors_in_col_major:
      new_minor_addr = 0
      new_col_addr += 1

    # Carry over col major to row major.
    if new_col_addr == num_col_majors:
      new_col_addr = 0
      new_row_addr += 1

    # Carry over row major to block type.
    num_rows = len(self.num_minors_per_std_colMajor[idcode])
    if new_row_addr == num_rows:
      new_row_addr = 0
      if new_block_type == FarBlockType.CLB_IO_CLK:
        new_block_type = FarBlockType.BRAM_CONTENT
      else:
        new_block_type = FarBlockType.CLB_IO_CLK

    return FrameAddressRegister(far.reserved, new_block_type, new_row_addr, new_col_addr, new_minor_addr, far.spec)

  # Returns True if the input FAR is the last one of its row.
  def is_last_far_of_row(
    self,
    idcode: int,
    far: FrameAddressRegister
  ) -> bool:
    (num_col_majors, num_minors_in_col_major) = self.get_colMajors_numMinors_count(idcode, far)

    is_last_col = far.col_addr == (num_col_majors - 1)
    is_last_minor = far.minor_addr == (num_minors_in_col_major - 1)

    return is_last_col and is_last_minor

# Represents a single configuration frame.
class ConfigFrame:
  def __init__(
    self,
    # Byte ofst in the bitstream at which this configuration frame is found.
    byte_ofst: int,
    words: np.ndarray,
    far: FrameAddressRegister,
    spec: ArchSpec
  ) -> None:
    assert words.dtype == bit_spec.BITSTREAM_ENDIANNESS, f"Error: Incorrect endianness."
    assert words.size == spec.frame_size_words(), f"Error: Expected config array at byte ofst {byte_ofst} to have size {spec.frame_size_words()} words, but is {words.size} words"
    self.byte_ofst = byte_ofst
    self.words = words
    self.far = far
    self.spec = spec

  def __str__(self) -> str:
    words_str = [
      f"{word:0>8x}"
      for word in self.words
    ]
    return f"BYTE_OFST = 0x{self.byte_ofst:0>8x}, {self.far}, WORDS_HEX = {words_str}"

  def bit(
    self,
    bit_ofst: int
  ) -> int:
    num_bits_word = self.words.itemsize * 8
    max_frame_ofst = self.spec.frame_size_words() * num_bits_word
    assert 0 <= bit_ofst < max_frame_ofst, f"Error: Expected frame offset to be in range [0 .. {max_frame_ofst}), but received {bit_ofst}"

    word_idx = bit_ofst // num_bits_word
    word_ofst = bit_ofst % num_bits_word
    target_word = self.words[word_idx]
    target_bit = helpers.bits(target_word, word_ofst, word_ofst)

    return target_bit

# Returns the frame bit offsets that differ between the input frames.
def diff_frame(
  baseline_frame: ConfigFrame,
  modified_frame: ConfigFrame
) -> list[int]:
  num_bits_word = baseline_frame.words.itemsize * 8

  frame_ofsts = list()
  for (word_idx, (baseline_word, modified_word)) in enumerate(zip(baseline_frame.words, modified_frame.words)):
    for bit_ofst_in_word in range(0, num_bits_word):
      baseline_bit = helpers.bits(baseline_word, bit_ofst_in_word, bit_ofst_in_word)
      modified_bit = helpers.bits(modified_word, bit_ofst_in_word, bit_ofst_in_word)

      if baseline_bit != modified_bit:
        bit_ofst_in_frame = word_idx * num_bits_word + bit_ofst_in_word
        frame_ofsts.append(bit_ofst_in_frame)

  return frame_ofsts
