# author: Sahand Kashani <sahand.kashani@epfl.ch>

import argparse
import typing
from collections import defaultdict
from pathlib import Path

import numpy as np

import format_json
import helpers
import resources
from bitstream import Bitstream
from device_summary import DeviceSummary
from frame import FrameAddressRegister


def extract_dsp_col_majors_from_bit(
  bit_a_path: str | Path,
  bit_b_path: str | Path,
  dsps_path: str | Path,
  out_path: str | Path
) -> None:
  bit_a = Bitstream.from_file_path(bit_a_path)
  bit_b = Bitstream.from_file_path(bit_b_path)

  diff_idcode_majorRow_majorCol = get_differing_major_columns(bit_a, bit_b)

  dsps: list[tuple[
    str, # Bottom-most DSP name in clock region column
    str  # Top-most DSP name in clock region column
  ]] = helpers.read_json(dsps_path)

  device_summary = resources.get_device_summary(bit_a.header.fpga_part)

  majors = get_majors(
    diff_idcode_majorRow_majorCol,
    dsps,
    device_summary
  )

  with open(out_path, "w") as f:
    json_str = format_json.emit(majors, sort_keys=True)
    f.write(json_str)

def get_differing_major_columns(
  bit_a: Bitstream,
  bit_b: Bitstream
) -> list[tuple[
  int, # idcode
  int, # major row
  int  # major col
]]:
  assert bit_a.header.fpga_part == bit_b.header.fpga_part, f"Error: bitstream part numbers do not match!"
  assert not bit_a.is_compressed(), f"Error: baseline bitstream is compressed!"
  assert not bit_a.is_encrypted(), f"Error: baseline bitstream is encrypted!"
  assert not bit_b.is_compressed(), f"Error:  bitstream is compressed!"
  assert not bit_b.is_encrypted(), f"Error:  bitstream is encrypted!"

  diff_idcodeFar = list[tuple[
    int,  # idcode
    FrameAddressRegister
  ]]()

  baseline = bit_a.get_per_far_configuration_arrays()
  modified = bit_b.get_per_far_configuration_arrays()

  for idcode in baseline:
    baseline_far_frames = baseline[idcode]
    modified_far_frames = modified[idcode]
    for (baseline_far, modified_far) in zip(baseline_far_frames, modified_far_frames):
      # Sanity check: The order of FARs should technically match as the bitstreams are generated using the same parameters.
      assert baseline_far == modified_far, f"Error: {baseline_far} != {modified_far}"
      baseline_frames = baseline_far_frames[baseline_far]
      modified_frames = modified_far_frames[modified_far]
      # Sanity check: The frames should be written once.
      assert len(baseline_frames) == len(modified_frames), f"Error: Number of writes to FAR {baseline_far} is different between bitstreams!"
      assert len(baseline_frames) == 1, f"Error: Expected a single write to FAR {baseline_far}, but there are {len(baseline_frames)}!"

      baseline_frame = baseline_frames[0]
      modified_frame = modified_frames[0]

      if not np.array_equal(baseline_frame.words, modified_frame.words):
        # print(f"FAR {baseline_far} differs")
        diff_idcodeFar.append((idcode, baseline_far))

  # Many minor frames will differ in the same major column. We don't care about
  # the minors and only need the (slr_name, major_row, major_col) for every DSP.
  # This will cause duplicates to appear, so we filter them out with a dictionary
  # (Python dictionaires maintain insertion order and can remove duplciates efficiently).
  #
  # Why do we need to store idcode (why not rely only on the major row)?
  # Because major rows are defined per SLR in the frame address register fields.
  # The "absolute" Y-value that you see in a clock region name (like X7Y15) is
  # not the major row. The major row is relative to each SLR.
  idcode_majorRow_majorCol = list(
    dict.fromkeys(
      [(idcode, far.row_addr, far.col_addr) for (idcode, far) in diff_idcodeFar]
    )
  )

  return idcode_majorRow_majorCol

def get_majors(
  diff_idcode_majorRow_majorCol: list[tuple[
    int, # idcode
    int, # major row
    int # major col
  ]],
  dsps: list[tuple[
    str, # Bottom-most DSP name in clock region column
    str  # Top-most DSP name in clock region column
  ]],
  device_summary: DeviceSummary
) -> dict[str, typing.Any]:

  # The final dict we return uses SLR names as keys, so we need a mapping from IDCODE to SLR name.
  idcode_to_slr = dict[int, str]()
  num_slrs = device_summary.num_slrs
  for slr_idx in range(0, num_slrs):
    slr_name = f"SLR{slr_idx}"
    idcode = device_summary.get_slr_idcode(slr_name)
    idcode_to_slr[idcode] = slr_name

  # Group differing frame addresses by their SLR and major row. This is because there are more major columns that differ
  # in a major row compared to the number of DSPs that have been instantiated, so we need to identify which of the
  # columns actually correspond to DSPs.

  # Furthermore, since the DSPs are being driven by constants, some CLB columns are being used to generate the constant
  # and CLB interconnect is also being used to route the constants to the DSPs. We therefore filter out any columns we
  # know to be CLB columns (this is available in the device summary).

  diff_slrNameMajorRow_majorCols: dict[tuple[str, int], list[int]] = defaultdict(list)
  for (idcode, major_row, major_col) in diff_idcode_majorRow_majorCol:
    slr_name = idcode_to_slr[idcode]
    slr_clb_col_majors: set[int] = device_summary.get_clb_col_majors(slr_name, major_row).values()

    # # Debug
    # num_minors_per_std_colMajor = slr_row_summary["num_minors_per_std_colMajor"]
    # num_minors = num_minors_per_std_colMajor[major_col]
    # print(f"(slr, major_row, major_col) = ({slr_name}, {major_row}, {major_col}) -> {num_minors} minors")

    # Only add a major column to the list of differing columns if we know it is not a CLB column.
    is_clb_column = major_col in slr_clb_col_majors
    if not is_clb_column:
      diff_slrNameMajorRow_majorCols[(slr_name, major_row)].append(major_col)

  # At this point we have filtered out CLB columns (the ones that generate the constants feeding the DSPs).
  # What remains is to eliminate the CLB interconnect columns. Here we use an additional hypothesis that
  # CLB interconnect columns require significantly more minor frames to configure than DSP columns.
  # We therefore count how many minors there are in the major columns that remain and take entries that have
  # fewer minors as the DSP columns.

  # The simplest way to do this is with a 2-pass algorithm:
  # - Pass 1: Find the largest minor frames count in the major columns. These correspond to CLB interconnect col majors.
  # - Pass 2: Select the major columns that have a different minor frame count to the number found in pass 1.

  # Why do we find the size of the interconnect (max minor count) and select columns that have a SMALLER number of
  # minors to find DSPs, instead of finding the size of the DSP (min minor count) and select columns that have EXACTLY
  # the same number of minors choose DSPs?
  #
  # The reason is that in US devices the DSP columns do not all have the same number of minors (oddly). Most of them
  # have 4 minors in DSP columns, but some have 6. Here's an extract from the xcku025 to show this:
  #
  #   (slr, major_row, major_col) = (SLR0, 2, 142) -> 4 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 143) -> 12 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 144) -> 58 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 149) -> 12 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 150) -> 58 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 151) -> 6 minors    <<< more minors in DSP column.
  #   (slr, major_row, major_col) = (SLR0, 2, 152) -> 12 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 153) -> 58 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 155) -> 12 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 156) -> 58 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 157) -> 4 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 158) -> 12 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 159) -> 58 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 161) -> 12 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 162) -> 58 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 163) -> 4 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 164) -> 12 minors
  #   (slr, major_row, major_col) = (SLR0, 2, 165) -> 58 minors
  #
  # Looking at the floormap of this device, we infer that the DSP columns that have 6 minors (instead of 4) are the ones
  # at the horizontal boundary between 2 clock regions.
  #
  # This is why we find the size of the CLB interconnect and keep all columns that are smaller as the DSP ones.

  # Pass 1
  # Just choose a large number as this will ultimately become the maximum minor count
  # among the remaining major columns.
  max_num_minors: int = -1
  for ((slr_name, major_row), major_cols) in diff_slrNameMajorRow_majorCols.items():
    num_minors_per_std_colMajor = device_summary.get_num_minors_per_std_col_major(slr_name, major_row)
    for major_col in major_cols:
      num_minors = num_minors_per_std_colMajor[major_col]
      max_num_minors = max(max_num_minors, num_minors)

  # Pass 2
  slrName_majorRow_dspMajorCols: dict[tuple[str, int], list[int]] = defaultdict(list)
  for ((slr_name, major_row), major_cols) in diff_slrNameMajorRow_majorCols.items():
    num_minors_per_std_colMajor = device_summary.get_num_minors_per_std_col_major(slr_name, major_row)
    for major_col in major_cols:
      num_minors = num_minors_per_std_colMajor[major_col]
      if num_minors < max_num_minors:
        slrName_majorRow_dspMajorCols[(slr_name, major_row)].append(major_col)

  # print(slrName_majorRow_dspMajorCols)

  # Some major rows have fewer DSPs than others as hard processors (or some other resource) may be taking up their place.
  # We now match the DSPs that were instantiated in the design with the columns we have identified. This will take care
  # of any "holes" in the design.

  slrNameMajorRow_dspXs: dict[
    tuple[
      str, # slr name
      int # major row
    ],
    list[int] # dsp x-coordinates in given major row
  ] = defaultdict(list)

  slrNameMajorRow_dspYBoundaries: dict[
    tuple[
      str, # slr name
      int # major row
    ],
    tuple[
      int, # bottom-most DSP in clock region Y-offset
      int # top-most DSP in clock region Y-offset
    ]
  ] = dict()

  # cr = clock region
  # The cr_row_idx below is the Y-value of the clock region. It is not the major row!
  # The major row is relative to each SLR.
  for (slr_name, cr_row_idx, cr_dsp_bottom, cr_dsp_top) in dsps:
    min_clock_region_row_idx = device_summary.get_min_clock_region_row_idx(slr_name)
    major_row = cr_row_idx - min_clock_region_row_idx

    pattern = r"DSP48E2_X(?P<x>\d+)Y(?P<y>\d+)"
    match_bottom = helpers.regex_match(pattern, cr_dsp_bottom)
    match_top = helpers.regex_match(pattern, cr_dsp_top)
    (dsp_bottom_x, dsp_bottom_y) = (int(match_bottom.group("x")), int(match_bottom.group("y")))
    (dsp_top_x, dsp_top_y) = (int(match_top.group("x")), int(match_top.group("y")))
    assert dsp_bottom_x == dsp_top_x, f"Error: Expected DSPs to be in the same column!"

    # print(f"{cr_dsp_bottom} -> (slrName, majorRow) = ({slr_name}, {major_row})")

    slrNameMajorRow_dspXs[(slr_name, major_row)].append(dsp_bottom_x)
    slrNameMajorRow_dspYBoundaries[(slr_name, major_row)] = (dsp_bottom_y, dsp_top_y)

  # print(slrNameMajorRow_dspXs)
  # print(slrNameMajorRow_dspYBoundaries)

  # We now have all the information we need and can format it as a dict that we will ultimately write to a JSON file.
  #
  # We want the resulting dictionary to look liks this:
  #
  #   {
  #     "slrs": {
  #       "SLR0": {
  #         "DSP": {
  #           "rowMajors": {
  #             "0": {
  #               "min_dsp_y_ofst": c,
  #               "max_dsp_y_ofst": d,
  #               "colMajors": {
  #                 "0": x,
  #                 "1": y,
  #                 ...
  #               }
  #             },
  #             "1": {
  #               "min_dsp_y_ofst": e, // Can be different from value above in HBM devices as the bottom-most major row has less DSPs (place is used by HBM pins instead).
  #               "max_dsp_y_ofst": f, // Can be different from value above in HBM devices as the bottom-most major row has less DSPs (place is used by HBM pins instead).
  #               "colMajors": {
  #                 "0": a,
  #                 "1": b,
  #                 ...
  #               }
  #             },
  #             ...
  #           }
  #         },
  #         ...
  #       }
  #     }
  #   }

  res = defaultdict(
    lambda: defaultdict(
      lambda: defaultdict(
        lambda: defaultdict(
          lambda: defaultdict(
            lambda: defaultdict(dict)
          )
        )
      )
    )
  )

  for (slr_name, major_row) in slrName_majorRow_dspMajorCols:
    dsp_majorCols = slrName_majorRow_dspMajorCols[(slr_name, major_row)]
    dsp_Xs = slrNameMajorRow_dspXs[(slr_name, major_row)]
    (dsp_bottom_y, dsp_top_y) = slrNameMajorRow_dspYBoundaries[(slr_name, major_row)]
    # print(f"(slr, row) = ({slr_name}, {major_row})")
    # print(f"dsp_majorCols = {dsp_majorCols}")
    # print(f"dsp_Xs        = {dsp_Xs}")
    assert len(dsp_majorCols) == len(dsp_Xs), f"Error: Expected the same number of DSP major columns as the number of DSPs in relative major row {major_row} in {slr_name}"

    res["slrs"][slr_name]["DSP"]["rowMajors"][str(major_row)]["min_dsp_y_ofst"] = dsp_bottom_y
    res["slrs"][slr_name]["DSP"]["rowMajors"][str(major_row)]["max_dsp_y_ofst"] = dsp_top_y
    for (dsp_majorCol, dsp_x) in zip(dsp_majorCols, dsp_Xs):
      res["slrs"][slr_name]["DSP"]["rowMajors"][str(major_row)]["colMajors"][str(dsp_x)] = dsp_majorCol

  return res

# Main program (if executed as script)
if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Extracts major column addresses of DSPs by comparing a blank bitstream with a modified one.")
  parser.add_argument("bit_a", type=str, help="Empty bitstream (with header).")
  parser.add_argument("bit_b", type=str, help="Target bitstream (with header).")
  parser.add_argument("dsps_json", type=str, help="JSON file listing the DSPs that have been instantiated (in order in the bitstream).")
  parser.add_argument("out_json", type=str, help="Output JSON file containing major col addresses that differ.")
  args = parser.parse_args()

  extract_dsp_col_majors_from_bit(args.bit_a, args.bit_b, args.dsps_json, args.out_json)

  print("Done")
