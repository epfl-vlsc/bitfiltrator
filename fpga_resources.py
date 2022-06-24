# author: Sahand Kashani <sahand.kashani@epfl.ch>

import enum

import numpy as np

import fpga_resources_spec as fpgares_spec
import helpers


class LutInput(enum.IntEnum):
  I0 = 0
  I1 = 1
  I2 = 2
  I3 = 3
  I4 = 4
  I5 = 5

class Lut:
  def __init__(
    self,
    # A single long 64-bit binary number with MSb on the left and LSb on the right.
    init_bin: str = None
  ) -> None:
    self._init = np.zeros(fpgares_spec.LEN_LUT_BITS // 8, dtype=np.uint8)
    # The binary number "<I5><I4><I3><I2><I1><I0>" is the index into the truth table.
    self._inputs = [
      LutInput.I5,
      LutInput.I4,
      LutInput.I3,
      LutInput.I2,
      LutInput.I1,
      LutInput.I0
    ]

    if init_bin is not None:
      assert len(init_bin) == fpgares_spec.LEN_LUT_BITS, f"Error: Expected {fpgares_spec.LEN_LUT_BITS}-bit string as lut initial value (received input of length {len(init_bin)})"
      assert helpers.is_binary_str(init_bin), f"Error: lut initialization vector is not binary-valued"

      # INIT values are written in human readable binary form. Bit 0 is on the right, and bit 63 is
      # on the left. Storing the INIT values as-is would require us to access index 63 to read
      # the value of bit 0. We reverse the value to get around this issue.
      for idx in range(fpgares_spec.LEN_LUT_BITS):
        idx_rev = fpgares_spec.LEN_LUT_BITS - 1 - idx
        bit_value = int(init_bin[idx_rev])
        helpers.np_write_bit(self._init, idx, bit_value)

  def to_bin(self) -> str:
    words_bin_str = [f"{word:0>8b}" for word in self._init]
    # We reverse so we can put the most significant word on the left.
    return "".join(reversed(words_bin_str))

  def to_hex(self) -> str:
    words_hex_str = [f"{word:0>2x}" for word in self._init]
    # We reverse so we can put the most significant word on the left.
    return "".join(reversed(words_hex_str))

  def set_bit(
    self,
    idx: int,
    value: int
  ) -> None:
    assert 0 <= idx < fpgares_spec.LEN_LUT_BITS, f"Error: Invalid index {idx}"
    helpers.np_write_bit(self._init, idx, value)

  def get_bit(
    self,
    idx: int
  ) -> int:
    assert 0 <= idx < fpgares_spec.LEN_LUT_BITS, f"Error: Invalid index {idx}"
    return helpers.np_read_bit(self._init, idx)

  def compute_output(
    self,
    I0: bool,
    I1: bool,
    I2: bool,
    I3: bool,
    I4: bool,
    I5: bool
  ) -> bool:
    # "tf" is True/False
    idx = sum([tf * 2**i for (i, tf) in zip([5, 4, 3, 2, 1, 0], [I5, I4, I3, I2, I1, I0])])
    return bool(self.get_bit(idx))

  def is_input_unused(
    self,
    lut_input: LutInput
  ) -> bool:
    num_inputs = len(LutInput)
    lut_input_idx: int = lut_input.value

    # To test whether an input IX is unused, we compare the output of the truth table
    # when IX is 0/1 for all combinations of the *other* inputs. If there is no combination
    # of inputs whose output changes when toggling IX from 0/1, the input is independent.

    for other_inputs_int in range(2 ** (num_inputs-1)):
      # When reading a binary number the MSb is on the left and the LSb on the right. Accessing
      # element 0 of the string will result in returning the MSb instead of the LSb, so I reverse
      # the string such that element 0 corresponds to the LSb when indexing.
      other_inputs_bin = f"{other_inputs_int:0>{num_inputs-1}b}"[::-1]

      # We compute the index of the truth table entries to check by slicing the binary string and
      # inserting a 0/1 at position {lut_input_idx}. We then reverse the binary string so that we
      # can transform it back to an integer form.
      res_0_idx_bin = f"{other_inputs_bin[:lut_input_idx]}0{other_inputs_bin[lut_input_idx:]}"[::-1]
      res_1_idx_bin = f"{other_inputs_bin[:lut_input_idx]}1{other_inputs_bin[lut_input_idx:]}"[::-1]
      res_0_idx_int = int(res_0_idx_bin, 2)
      res_1_idx_int = int(res_1_idx_bin, 2)

      # Check if the output of the function changes when IX is 0/1. If yes, the input is used.
      res_0 = self.get_bit(res_0_idx_int)
      res_1 = self.get_bit(res_1_idx_int)

      if res_0 != res_1:
        return False

    return True

  def get_unused_inputs(
    self
  ) -> list[LutInput]:
    return [li for li in self._inputs if self.is_input_unused(li)]

  def get_used_inputs(
    self
  ) -> list[LutInput]:
    return [li for li in self._inputs if not self.is_input_unused(li)]

class Bram:
  # The initialization values must be BIN instead of HEX simply because some entries are not multiples of 4 in length
  # (the register initial values are 18 bits for example). I have since dropped support for register initial values, but
  # I kept the input in binary in any case.
  def __init__(
    self,
    # A single long 16384-bit binary number with MSb on the left and LSb on the right.
    init_mem_bin: str = None,
    # A single long 2048-bit binary number with MSb on the left and LSb on the right.
    init_parity_bin: str = None
  ):
    self.init_mem = np.zeros(fpgares_spec.LEN_BRAM_MEMORY_BITS // 8, dtype=np.uint8)
    self.init_parity = np.zeros(fpgares_spec.LEN_BRAM_PARITY_BITS // 8, dtype=np.uint8)

    # INIT values are written in human readable binary form. Bit 0 is on the right, and bit 255 (INIT)
    # and 17 (INITP) is on the left.
    # Storing the INIT values as-is would require us to access index 255 (INIT) and 17 (INITP) to read
    # the value of bit 0. We reverse the value to get around this issue.

    if init_mem_bin is not None:
      assert len(init_mem_bin) == fpgares_spec.LEN_BRAM_MEMORY_BITS, f"Error: Expected {fpgares_spec.LEN_BRAM_MEMORY_BITS}-bit string as bram content initial value (received input of length {len(init_mem_bin)})"
      assert helpers.is_binary_str(init_mem_bin), f"Error: bram content initialization vector is not binary-valued"

      for idx in range(fpgares_spec.LEN_BRAM_MEMORY_BITS):
        idx_rev = fpgares_spec.LEN_BRAM_MEMORY_BITS - 1 - idx
        bit_value = int(init_mem_bin[idx_rev])
        helpers.np_write_bit(self.init_mem, idx, bit_value)

    if init_parity_bin is not None:
      assert len(init_parity_bin) == fpgares_spec.LEN_BRAM_PARITY_BITS, f"Error: Expected {fpgares_spec.LEN_BRAM_PARITY_BITS}-bit string as bram parity initial value (received input of length {len(init_parity_bin)})"
      assert helpers.is_binary_str(init_parity_bin), f"Error: bram parity initialization vector is not binary-valued"

      for idx in range(fpgares_spec.LEN_BRAM_PARITY_BITS):
        idx_rev = fpgares_spec.LEN_BRAM_PARITY_BITS - 1 - idx
        bit_value = int(init_parity_bin[idx_rev])
        helpers.np_write_bit(self.init_parity, idx, bit_value)

  def set_mem_bit(
    self,
    idx: int,
    value: int
  ) -> None:
    assert 0 <= idx < fpgares_spec.LEN_BRAM_MEMORY_BITS, f"Error: Invalid index {idx}"
    helpers.np_write_bit(self.init_mem, idx, value)

  def set_parity_bit(
    self,
    idx: int,
    value: int
  ) -> None:
    assert 0 <= idx < fpgares_spec.LEN_BRAM_PARITY_BITS, f"Error: Invalid index {idx}"
    helpers.np_write_bit(self.init_parity, idx, value)

  def get_mem_bit(
    self,
    idx: int
  ) -> int:
    assert 0 <= idx < fpgares_spec.LEN_BRAM_MEMORY_BITS, f"Error: Invalid index {idx}"
    return helpers.np_read_bit(self.init_mem, idx)

  def get_parity_bit(
    self,
    idx: int
  ) -> int:
    assert 0 <= idx < fpgares_spec.LEN_BRAM_PARITY_BITS, f"Error: Invalid index {idx}"
    return helpers.np_read_bit(self.init_parity, idx)

  def mem_to_bin(self) -> str:
    words_bin_str = [f"{word:0>8b}" for word in self.init_mem]
    # We reverse so we can put the most significant word on the left.
    return "".join(reversed(words_bin_str))

  def parity_to_bin(self) -> str:
    words_bin_str = [f"{word:0>8b}" for word in self.init_parity]
    # We reverse so we can put the most significant word on the left.
    return "".join(reversed(words_bin_str))

  def mem_to_hex(self) -> str:
    words_hex_str = [f"{word:0>2x}" for word in self.init_mem]
    # We reverse so we can put the most significant word on the left.
    return "".join(reversed(words_hex_str))

  def parity_to_hex(self) -> str:
    words_hex_str = [f"{word:0>2x}" for word in self.init_parity]
    # We reverse so we can put the most significant word on the left.
    return "".join(reversed(words_hex_str))
