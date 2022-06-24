# author: Sahand Kashani <sahand.kashani@epfl.ch>

import helpers
import resources
from arch_spec import ArchSpec, UltraScaleSpec
from frame import FrameAddressRegister
from frame_spec import FarBlockType


class BitLocator:
  def __init__(
    self,
    fpga_part: str
  ) -> None:
    self._arch_summary = resources.get_arch_summary(fpga_part)
    self._device_summary = resources.get_device_summary(fpga_part)
    self._ar_spec = ArchSpec.create_spec(fpga_part)
    self._clb_pattern = r"^SLICE_X(?P<x>\d+)Y(?P<y>\d+)/(?P<bel>[ABCDEFGH](6LUT|FF2?))$"
    self._bram_pattern = r"^RAMB(?P<size_kb>\d+)_X(?P<x>\d+)Y(?P<y>\d+)$"

  def locate_reg(
    self,
    name: str
  ) -> tuple[
    str, # Target SLR name
    FrameAddressRegister, # Target frame address
    int # Frame offset (in bits)
  ]:
    match = helpers.regex_match(self._clb_pattern, name)
    bel_x = int(match.group("x"))
    bel_y = int(match.group("y"))
    bel_name = match.group("bel")

    slr_name = self._get_slr_name(bel_y, self._ar_spec.num_clb_per_column())
    row_major = self._get_row_major(bel_y, slr_name, self._ar_spec.num_clb_per_column())
    (col_major, col_tile_type) = self._get_col_major(bel_x, slr_name, row_major, FarBlockType.CLB_IO_CLK)

    # Encodings are per-column, so we compute the relative offset of the BEL's y-value in a CLB column.
    y_ofst = bel_y % self._ar_spec.num_clb_per_column()
    (minor, frame_ofst) = self._arch_summary.get_reg_loc(col_tile_type, y_ofst, bel_name)

    far = FrameAddressRegister(
      reserved=0,
      block_type=FarBlockType.CLB_IO_CLK,
      row_addr=row_major,
      col_addr=col_major,
      minor_addr=minor,
      spec=self._ar_spec
    )

    return (slr_name, far, frame_ofst)

  def locate_lut(
    self,
    name: str
  ) -> tuple[
    str, # Target SLR name
    list[FrameAddressRegister], # Target frame addresses (one per LUT bit)
    list[int] # Frame offset (in bits, one per LUT bit)
  ]:
    match = helpers.regex_match(self._clb_pattern, name)
    bel_x = int(match.group("x"))
    bel_y = int(match.group("y"))
    bel_name = match.group("bel")

    slr_name = self._get_slr_name(bel_y, self._ar_spec.num_clb_per_column())
    row_major = self._get_row_major(bel_y, slr_name, self._ar_spec.num_clb_per_column())
    (col_major, col_tile_type) = self._get_col_major(bel_x, slr_name, row_major, FarBlockType.CLB_IO_CLK)

    # Encodings are per-column, so we compute the relative offset of the BEL's y-value in a CLB column.
    y_ofst = bel_y % self._ar_spec.num_clb_per_column()

    (minors, frame_ofsts) = self._arch_summary.get_lut_loc(col_tile_type, y_ofst, bel_name)

    fars = [
      FrameAddressRegister(
        reserved=0,
        block_type=FarBlockType.CLB_IO_CLK,
        row_addr=row_major,
        col_addr=col_major,
        minor_addr=minor,
        spec=self._ar_spec
      )
      for minor in minors
    ]

    return (slr_name, fars, frame_ofsts)

  def locate_bram(
    self,
    name: str
  ) -> tuple[
    str, # Target SLR name
    list[FrameAddressRegister], # Target frame addresses (one per BRAM content bit)
    list[int], # Frame offset (in bits, one per BRAM content bit)
    list[FrameAddressRegister], # Target frame addresses (one per BRAM parity bit)
    list[int] # Frame offset (in bits, one per BRAM parity bit)
  ]:
    match = helpers.regex_match(self._bram_pattern, name)
    size_kb = int(match.group("size_kb"))
    bel_x = int(match.group("x"))
    bel_y = int(match.group("y"))

    assert size_kb == 18, f"Error: Only 18K BRAM encodings are supported for now."
    slr_name = self._get_slr_name(bel_y, self._ar_spec.num_18k_bram_per_column())
    row_major = self._get_row_major(bel_y, slr_name, self._ar_spec.num_18k_bram_per_column())
    (col_major, col_tile_type) = self._get_col_major(bel_x, slr_name, row_major, FarBlockType.BRAM_CONTENT)

    # Encodings are per-column, so we compute the relative offset of the BEL's y-value in a BRAM column.
    y_ofst = bel_y % self._ar_spec.num_18k_bram_per_column()
    (mem_minors, mem_frame_ofsts) = self._arch_summary.get_bram_mem_loc(y_ofst)
    (parity_minors, parity_frame_ofsts) = self._arch_summary.get_bram_parity_loc(y_ofst)

    mem_fars = [
      FrameAddressRegister(
        reserved=0,
        block_type=FarBlockType.BRAM_CONTENT,
        row_addr=row_major,
        col_addr=col_major,
        minor_addr=minor,
        spec=self._ar_spec
      )
      for minor in mem_minors
    ]

    parity_fars = [
      FrameAddressRegister(
        reserved=0,
        block_type=FarBlockType.BRAM_CONTENT,
        row_addr=row_major,
        col_addr=col_major,
        minor_addr=minor,
        spec=self._ar_spec
      )
      for minor in parity_minors
    ]

    return (slr_name, mem_fars, mem_frame_ofsts, parity_fars, parity_frame_ofsts)

  def _get_min_max_row_majors_in_slr(
    self,
    slr_name: str
  ) -> tuple[int, int]:
    min_rowMajor = self._device_summary.get_min_clock_region_row_idx(slr_name)
    max_rowMajor = self._device_summary.get_max_clock_region_row_idx(slr_name)
    return (min_rowMajor, max_rowMajor)

  def _get_slr_name(
    self,
    bel_y: int,
    num_bel_per_column: int
  ) -> str:
    # Compute min/max Y-value of the specific BEL type in every SLR.
    slr_minMaxY: dict[str, tuple[int, int]] = dict()
    for slr_name in self._device_summary.get_slr_names():
      (min_rowMajor, max_rowMajor) = self._get_min_max_row_majors_in_slr(slr_name)
      min_y = min_rowMajor * num_bel_per_column
      max_y = (max_rowMajor + 1) * num_bel_per_column - 1
      slr_minMaxY[slr_name] = (min_y, max_y)

    # Locate which SLR the BEL is in.
    target_slrName = None
    for (slr_name, (min_y, max_y)) in slr_minMaxY.items():
      if min_y <= bel_y <= max_y:
        target_slrName = slr_name

    assert target_slrName is not None, f"Error: Could not locate SLR for BEL at index {bel_y}"
    return target_slrName

  def _get_row_major(
    self,
    bel_y: int,
    # SLR in which the BEL is located. It can technically be recomputed here, but we assume
    # it is provided by the user instead.
    slr_name: str,
    num_bel_per_column: int
  ) -> int:
    # Compute min/max Y-value of the specific BEL type in every SLR row.
    rowMajor_minMaxY: dict[int, tuple[int, int]] = dict()
    (min_rowMajor, max_rowMajor) = self._get_min_max_row_majors_in_slr(slr_name)
    for rowMajor in range(min_rowMajor, max_rowMajor + 1):
      min_y = rowMajor * num_bel_per_column
      max_y = (rowMajor + 1) * num_bel_per_column - 1
      rowMajor_minMaxY[rowMajor] = (min_y, max_y)

    # Locate which row major the BEL is in.
    abs_rowMajor = None
    for (rowMajor, (min_y, max_y)) in rowMajor_minMaxY.items():
      if min_y <= bel_y <= max_y:
        abs_rowMajor = rowMajor

    assert abs_rowMajor is not None, f"Error: Could not locate row major for BEL at index {bel_y}"

    # The row major is numbered as  [0 .. max_clock_region_row] in vivado and spans *all* SLRs.
    # However, the row major in a frame address starts back at 0 in *every* SLR.
    # We therefore transform the absolute row major into a relative one before returning.

    rel_rowMajor = abs_rowMajor - min_rowMajor
    return rel_rowMajor

  def _get_col_major(
    self,
    bel_x: int,
    # SLR in which the BEL is located.
    slr_name: str,
    # Row major in which the BEL is located. This is the *relative* row major
    # inside the target SLR.
    row_major: int,
    block_type: FarBlockType
  ) -> tuple[
    int, # Column major
    str # Tile type
  ]:
    assert block_type in {FarBlockType.CLB_IO_CLK, FarBlockType.BRAM_CONTENT}, f"Error: Cannot generate col major for unknown block type {block_type}"

    if block_type == FarBlockType.CLB_IO_CLK:
      # The x-value is the CLB column number. We lookup the device resource file to map this
      # logical CLB column number to a physical major column number.
      colMajor = self._device_summary.get_clb_col_majors(slr_name, row_major)[bel_x]
      tileType = self._device_summary.get_clb_tile_types(slr_name, row_major)[bel_x]
    else:
      colMajor = self._device_summary.get_bram_content_col_majors(slr_name, row_major)[bel_x]
      # All BRAM columns have the same tile type.
      tileType = "BRAM"

    return (colMajor, tileType)
