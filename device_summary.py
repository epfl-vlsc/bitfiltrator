# author: Sahand Kashani <sahand.kashani@epfl.ch>

import typing

from frame_spec import FarBlockType


class DeviceSummary:
  def __init__(
    self,
    summary: dict[str, typing.Any]
  ) -> None:
    self.device: str = summary["device"]
    self.part: str = summary["part"]
    self.license: str = summary["license"]
    self.num_brams: int = int(summary["num_brams"])
    self.num_dsps: int = int(summary["num_dsps"])
    self.num_luts: int = int(summary["num_luts"])
    self.num_regs: int = int(summary["num_regs"])
    self.num_slices: int = int(summary["num_slices"])
    self.num_slrs: int = int(summary["num_slrs"])

    self.tileType_siteType_pairs: list[tuple[str, str]] = [tuple(pair) for pair in summary["tileType_siteType_pairs"]]

    self._slrNames = list[str]()
    self._slrIdcode_slrName = dict[int, str]() # slrIdcode -> str
    self._slrName_idcode = dict[str, int]() # slrName -> int
    self._slrName_slrIdx = dict[str, int]() # slrName -> int
    self._slrName_configOrderIdx = dict[str, int]() # slrName -> int
    self._slrName_minClockRegionRowIdx = dict[str, int]() # slrName -> int
    self._slrName_maxClockRegionRowIdx = dict[str, int]() # slrName -> int
    self._slrName_minClockRegionColIdx = dict[str, int]() # slrName -> int
    self._slrName_maxClockRegionColIdx = dict[str, int]() # slrName -> int
    self._slrName_minFarRowIdx = dict[str, int]() # slrName -> int
    self._slrName_maxFarRowIdx = dict[str, int]() # slrName -> int
    self._slrNameRowMajor_bramContentColMajors = dict[tuple[str, int], dict[int, int]]() # (slrName, rowMajor) -> dict[bram_x, bram_colMajor]
    self._slrNameRowMajor_bramParityColMajors = dict[tuple[str, int], dict[int, int]]() # (slrName, rowMajor) -> dict[bram_x, bram_colMajor]
    self._slrNameRowMajor_bramRegColMajors = dict[tuple[str, int], dict[int, int]]() # (slrName, rowMajor) -> dict[bram_x, std_colMajor]
    self._slrNameRowMajor_dspColMajors = dict[tuple[str, int], dict[int, int]]() # (slrName, rowMajor) -> dict[dsp_x, std_colMajor]
    self._slrNameRowMajor_clbColMajors = dict[tuple[str, int], dict[int, int]]() # (slrName, rowMajor) -> dict[slice_x, std_colMajor]
    self._slrNameRowMajor_clbTileTypes = dict[tuple[str, int], dict[int, str]]() # (slrName, rowMajor) -> dict[slice_x, tile_type]
    self._slrNameRowMajor_numMinorsPerBramContentColMajor = dict[tuple[str, int], list[int]]() # (slrName, rowMajor) -> list[int]
    self._slrNameRowMajor_numMinorsPerStdColMajor = dict[tuple[str, int], list[int]]() # (slrName, rowMajor) -> list[int]

    self.slr_dict = dict[str, dict]()
    for (slrName, slrProperties) in summary["slrs"].items():
      slr_idx: int = slrProperties["slr_idx"]
      config_order_idx: int = slrProperties["config_order_idx"]
      idcode: int = int(slrProperties["idcode"], 16)
      min_clock_region_row_idx: int = slrProperties["min_clock_region_row_idx"]
      max_clock_region_row_idx: int = slrProperties["max_clock_region_row_idx"]
      min_clock_region_col_idx: int = slrProperties["min_clock_region_col_idx"]
      max_clock_region_col_idx: int = slrProperties["max_clock_region_col_idx"]
      min_far_row_idx: int = slrProperties["min_far_row_idx"]
      max_far_row_idx: int = slrProperties["max_far_row_idx"]

      self._slrNames.append(slrName)
      self._slrIdcode_slrName[idcode] = slrName
      self._slrName_idcode[slrName] = idcode
      self._slrName_slrIdx[slrName] = slr_idx
      self._slrName_configOrderIdx[slrName] = config_order_idx
      self._slrName_minClockRegionRowIdx[slrName] = min_clock_region_row_idx
      self._slrName_maxClockRegionRowIdx[slrName] = max_clock_region_row_idx
      self._slrName_minClockRegionColIdx[slrName] = min_clock_region_col_idx
      self._slrName_maxClockRegionColIdx[slrName] = max_clock_region_col_idx
      self._slrName_minFarRowIdx[slrName] = min_far_row_idx
      self._slrName_maxFarRowIdx[slrName] = max_far_row_idx

      for (rowMajor_str, rowMajorProperties) in slrProperties["rowMajors"].items():
        rowMajor_int = int(rowMajor_str)

        # These fields are not always present if we are in a row that is hidden
        # from the user (hidden in vivado), so we use `dict.get` instead of directly
        # indexing the rowMajorProperties.
        bram_content_colMajors: dict[str, int] = rowMajorProperties.get("bram_content_colMajors", dict())
        bram_parity_colMajors: dict[str, int] = rowMajorProperties.get("bram_content_parity_colMajors", dict())
        bram_reg_colMajors: dict[str, int] = rowMajorProperties.get("bram_reg_colMajors", dict())
        dsp_colMajors: dict[str, int] = rowMajorProperties.get("dsp_colMajors", dict())
        clb_colMajors: dict[str, int] = rowMajorProperties.get("clb_colMajors", dict())
        clb_tileTypes: dict[str, str] = rowMajorProperties.get("clb_tileTypes", dict())
        # These fields should always exist though.
        num_minors_per_bram_content_colMajor: list[int] = rowMajorProperties["num_minors_per_bram_content_colMajor"]
        num_minors_per_std_colMajor: list[int] = rowMajorProperties["num_minors_per_std_colMajor"]

        # Sanity check
        bram_spec_lengths = set(map(len, [
          bram_content_colMajors,
          bram_parity_colMajors,
          bram_reg_colMajors,
        ]))
        clb_spec_lengths = set(map(len, [
          clb_colMajors,
          clb_tileTypes
        ]))
        assert len(bram_spec_lengths) == 1, f"Error: bram specs have different lengths at row major {rowMajor_int}"
        assert len(clb_spec_lengths), f"Error: clb specs have different lengths at row major {rowMajor_int}"

        self._slrNameRowMajor_bramContentColMajors[(slrName, rowMajor_int)] = {int(k): v for (k, v) in bram_content_colMajors.items()}
        self._slrNameRowMajor_bramParityColMajors[(slrName, rowMajor_int)] = {int(k): v for (k, v) in bram_parity_colMajors.items()}
        self._slrNameRowMajor_bramRegColMajors[(slrName, rowMajor_int)] = {int(k): v for (k, v) in bram_reg_colMajors.items()}
        self._slrNameRowMajor_dspColMajors[(slrName, rowMajor_int)] = {int(k): v for (k, v) in dsp_colMajors.items()}
        self._slrNameRowMajor_clbColMajors[(slrName, rowMajor_int)] = {int(k): v for (k, v) in clb_colMajors.items()}
        self._slrNameRowMajor_clbTileTypes[(slrName, rowMajor_int)] = {int(k): v for (k, v) in clb_tileTypes.items()}
        self._slrNameRowMajor_numMinorsPerBramContentColMajor[(slrName, rowMajor_int)] = num_minors_per_bram_content_colMajor
        self._slrNameRowMajor_numMinorsPerStdColMajor[(slrName, rowMajor_int)] = num_minors_per_std_colMajor

  def get_slr_names(self) -> list[str]:
    return self._slrNames

  def get_config_order_idx(
    self,
    slr_name: str
  ) -> int:
    return self._slrName_configOrderIdx[slr_name]

  def get_slr_idx(
    self,
    slr_name: str
  ) -> int:
    return self._slrName_slrIdx[slr_name]

  def get_slr_idcode(
    self,
    slr_name: str
  ) -> int:
    return self._slrName_idcode[slr_name]

  def get_slr_name(
    self,
    idcode: int
  ) -> str:
    return self._slrIdcode_slrName[idcode]

  def get_min_clock_region_row_idx(
    self,
    slr_name: str
  ) -> int:
    return self._slrName_minClockRegionRowIdx[slr_name]

  def get_max_clock_region_row_idx(
    self,
    slr_name: str
  ) -> int:
    return self._slrName_maxClockRegionRowIdx[slr_name]

  def get_min_clock_region_col_idx(
    self,
    slr_name: str
  ) -> int:
    return self._slrName_minClockRegionColIdx[slr_name]

  def get_max_clock_region_col_idx(
    self,
    slr_name: str
  ) -> int:
    return self._slrName_maxClockRegionColIdx[slr_name]

  def get_min_far_row_idx(
    self,
    slr_name: str
  ) -> int:
    return self._slrName_minFarRowIdx[slr_name]

  def get_max_far_row_idx(
    self,
    slr_name: str
  ) -> int:
    return self._slrName_maxFarRowIdx[slr_name]

  def get_bram_content_col_majors(
    self,
    slr_name: str,
    row_major: int
  ) -> dict[
    int, # bram_x
    int # bram_colMajor
  ]:
    return self._slrNameRowMajor_bramContentColMajors[(slr_name, row_major)]

  def get_bram_parity_col_majors(
    self,
    slr_name: str,
    row_major: int
  ) -> dict[
    int, # bram_x
    int # bram_colMajor
  ]:
    return self._slrNameRowMajor_bramParityColMajors[(slr_name, row_major)]

  def get_bram_reg_col_majors(
    self,
    slr_name: str,
    row_major: int
  ) -> dict[
    int, # bram_x
    int # std_colMajor
  ]:
    return self._slrNameRowMajor_bramRegColMajors[(slr_name, row_major)]

  def get_dsp_col_majors(
    self,
    slr_name: str,
    row_major: int
  ) -> dict[
    int, # dsp_x
    int # std_colMajor
  ]:
    return self._slrNameRowMajor_dspColMajors[(slr_name, row_major)]

  def get_clb_col_majors(
    self,
    slr_name: str,
    row_major: int
  ) -> dict[
    int, # slice_x
    int # std_colMajor
  ]:
    return self._slrNameRowMajor_clbColMajors[(slr_name, row_major)]

  def get_clb_tile_types(
    self,
    slr_name: str,
    row_major: int
  ) -> dict[
    int, # slice_x
    str # tile_type
  ]:
    return self._slrNameRowMajor_clbTileTypes[(slr_name, row_major)]

  def get_num_minors_per_bram_content_col_major(
    self,
    slr_name: str,
    row_major: int
  ) -> list[int]:
    return self._slrNameRowMajor_numMinorsPerBramContentColMajor[(slr_name, row_major)]

  def get_num_minors_per_std_col_major(
    self,
    slr_name: str,
    row_major: int
  ) -> list[int]:
    return self._slrNameRowMajor_numMinorsPerStdColMajor[(slr_name, row_major)]

  def is_clb_col_major(
    self,
    slr_name: str,
    block_type: FarBlockType,
    row_major: int,
    col_major: int
  ) -> bool:
    is_config = block_type == FarBlockType.CLB_IO_CLK
    clb_colMajors = self.get_clb_col_majors(slr_name, row_major)
    is_clb_col = col_major in clb_colMajors
    return is_config and is_clb_col

  def is_bram_col_major(
    self,
    slr_name: str,
    block_type: FarBlockType,
    row_major: int,
    col_major: int
  ) -> bool:
    is_bram = block_type == FarBlockType.BRAM_CONTENT
    bram_colMajors = self.get_bram_content_col_majors(slr_name, row_major)
    is_bram_col = col_major in bram_colMajors
    return is_bram and is_bram_col
