# author: Sahand Kashani <sahand.kashani@epfl.ch>

import typing
from collections import defaultdict


class ArchSummary:
  def __init__(
    self,
    summary: dict[str, typing.Any]
  ) -> None:
    self._bram_mem_locs = dict[
      int, # Y_ofst
      tuple[
        tuple[int], # minors
        tuple[int] # frame_ofsts
      ]
    ]()

    self._bram_parity_locs = dict[
      int, # Y_ofst
      tuple[
        tuple[int], # minors
        tuple[int] # frame_ofsts
      ]
    ]()

    self._lut_locs: dict[
      str, # tile_type (CLEL_L, CLEL_R, ...)
      dict[
        int, # Y_ofst
        dict[
          str, # lut name (A6LUT, B6LUT, ...)
          tuple[
            tuple[int], # minors
            tuple[int] # frame_ofsts
          ]
        ]
      ]
    ] = defaultdict(
      lambda: defaultdict(
        lambda: defaultdict(tuple)
      )
    )

    self._reg_locs: dict[
      str, # tile_type (CLEL_L, CLEL_R, ...)
      dict[
        int, # Y_ofst
        dict[
          str, # reg name (AFF, BFF, ...)
          tuple[
            int, # minor
            int # frame_ofst
          ]
        ]
      ]
    ] = defaultdict(
      lambda: defaultdict(
        lambda: defaultdict(tuple)
      )
    )

    for (yOfst_str, yOfstProperties) in summary["BRAM"]["BramMemLoc"]["Y_ofst"].items():
      minors = yOfstProperties["minor"]
      frame_ofsts = yOfstProperties["frame_ofst"]
      # Sanity check
      assert len(minors) == len(frame_ofsts), f"Error: num minors and frame ofsts do not match"
      self._bram_mem_locs[int(yOfst_str)] = (tuple(minors), tuple(frame_ofsts))

    for (yOfst_str, yOfstProperties) in summary["BRAM"]["BramMemParityLoc"]["Y_ofst"].items():
      minors = yOfstProperties["minor"]
      frame_ofsts = yOfstProperties["frame_ofst"]
      assert len(minors) == len(frame_ofsts), f"Error: num minors and frame ofsts do not match"
      self._bram_parity_locs[int(yOfst_str)] = (tuple(minors), tuple(frame_ofsts))

    clb_tile_types = [k for k in summary.keys() if k.startswith("CLE")]
    for tile_type in clb_tile_types:
      tileTypeProperties = summary[tile_type]

      for (yOfst_str, yOfstProperties) in tileTypeProperties["LutLoc"]["Y_ofst"].items():
        minors_dict = yOfstProperties["minor"]
        frameOfsts_dict = yOfstProperties["frame_ofst"]
        bel_names = minors_dict.keys()
        for bel_name in bel_names:
          minors = minors_dict[bel_name]
          frame_ofsts = frameOfsts_dict[bel_name]
          assert len(minors) == len(frame_ofsts), f"Error: num minors and frame ofsts do not match"
          self._lut_locs[tile_type][int(yOfst_str)][bel_name] = (tuple(minors), tuple(frame_ofsts))

      for (yOfst_str, yOfstProperties) in tileTypeProperties["RegLoc"]["Y_ofst"].items():
        minors_dict = yOfstProperties["minor"]
        frameOfsts_dict = yOfstProperties["frame_ofst"]
        bel_names = minors_dict.keys()
        for bel_name in bel_names:
          # A register only has 1 minor and frame_ofst, so no assertion is needed here.
          minor = minors_dict[bel_name]
          frame_ofst = frameOfsts_dict[bel_name]
          self._reg_locs[tile_type][int(yOfst_str)][bel_name] = (minor, frame_ofst)

  def get_bram_mem_loc(
    self,
    y_ofst: int
  ) -> tuple[
    tuple[int], # minors (one per BRAM memory bit)
    tuple[int] # frame_ofsts (one per BRAM memory bit)
  ]:
    (minors, frame_ofsts) = self._bram_mem_locs[y_ofst]
    return (minors, frame_ofsts)

  def get_bram_parity_loc(
    self,
    y_ofst: int
  ) -> tuple[
    tuple[int], # minors (one per BRAM parity bit)
    tuple[int] # frame_ofsts (one per BRAM parity bit)
  ]:
    (minors, frame_ofsts) = self._bram_parity_locs[y_ofst]
    return (minors, frame_ofsts)

  def get_lut_loc(
    self,
    tile_type: str,
    y_ofst: int,
    bel_name: str
  ) -> tuple[
    tuple[int], # minors (one per LUT bit)
    tuple[int] # frame_ofsts (one per LUT bit)
  ]:
    (minors, frame_ofsts) = self._lut_locs[tile_type][y_ofst][bel_name]
    return (minors, frame_ofsts)

  def get_reg_loc(
    self,
    tile_type: str,
    y_ofst: int,
    bel_name: str
  ) -> tuple[
    int, # minor
    int # frame_ofst
  ]:
    (minor, frame_ofst) = self._reg_locs[tile_type][y_ofst][bel_name]
    return (minor, frame_ofst)
