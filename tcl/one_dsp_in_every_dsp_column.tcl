# To call this script, use the following command:
#
#   vivado -mode batch -source one_dsp_in_every_clb_column.tcl -notrace -tclargs <fpga_part> <bitstream_out> <dsp_out>
#
# Example:
#
#   vivado -mode batch -source one_dsp_in_every_clb_column.tcl -notrace -tclargs xcu250-figd2104-2L-e output.bit dsps.txt
#
# The outputs of this script are 3 files:
#   - <bitstream_out>
#   - dcp file (using same prefix as <bitstream_out> with ".dcp" extension)
#   - <dsp_out> file: a text file listing the DSPs instantiated in the design in order (incrementing across clock regions
#                     horizontally, then vertically)

package require struct::list

source [file join [file dirname [info script]] helpers.tcl]

set script_path [file dirname [file normalize [info script]]]

# Enumerates all candidate DSPs that should be used in the design IN ORDER. The DSP is the bottom-most and top-most
# one in each DSP column.
#
# Why do we need to also enumerate the top-most DSP in each clock region column? In all other experiments we only took
# the bottom-most resource (register, LUT, etc.).
# The reason is that FPGAs with HBM memory place the HBM pins in the bottom-most DSP column. It takes the space of SOME
# DSPs in the column, but not ALL (unlike LAGUNA cells for example which take up the full height of a CLB column).
#
# We therefore need the bottom- and top-most DSP of each column so we can accurately tell which (SLR, major_row) a DSP
# is located in given its name (DSP48E2_X<x>Y<y>).
proc get_candidate_dsps {} {
  puts "Enumerating DSPs"

  # Empty list we will populate.
  set saved_dsp_locs {}

  set dsp_site_pattern "DSP48E2_X(\\d+)Y(\\d+)"

  # Get the min/max SLR indices.
  lassign [get_slr_index_boundaries] min_slr_idx max_slr_idx

  # Iterate over SLRs in order.
  for {set slr_idx ${min_slr_idx}} {${slr_idx} <= ${max_slr_idx}} {incr slr_idx} {
    set slr [get_slrs -filter "SLR_INDEX == ${slr_idx}"]
    puts "Processing SLR ${slr}"

    # We want to iterate over the clock regions of the SLR in order. One might think an easy way of
    # doing this is to just call `lsort -dictionary [get_clock_regions -of_objects ${slr}]`, but
    # this is false. The command above would iterate over the clock regions in column order
    # {X0Y0, X0Y1, X0Y2, ..., X1Y0, ...}, whereas we want to iterate over the clock regions in row order
    # {X0Y0, X1Y0, X2Y0, ..., X0Y1, ...}.
    # We therefore resort to manual indexing to select the clock region of interest.

    # Get the min/max col/row index for the clock regions ("cr") in the current SLR.
    # Clock regions are the large tiles of the form "X(\d+)Y(\d+)".
    lassign [get_slr_clock_region_boundaries ${slr}] min_cr_col_idx max_cr_col_idx min_cr_row_idx max_cr_row_idx

    # Iterate over the clock regions of the SLR in order.
    for {set cr_row_idx ${min_cr_row_idx}} {${cr_row_idx} <= ${max_cr_row_idx}} {incr cr_row_idx} {
      for {set cr_col_idx ${min_cr_col_idx}} {${cr_col_idx} <= ${max_cr_col_idx}} {incr cr_col_idx} {
        set clock_region [get_clock_regions -of_objects ${slr} X${cr_col_idx}Y${cr_row_idx}]
        puts "Processing clock region ${clock_region}"

        set cr_tiles [get_tiles -quiet -of_objects ${clock_region}]

        # Some clock regions could have nothing inside them. This often happens in Zynq devices as
        # some clock regions are taken up by hard processors. These processors are not visible in the
        # floorplan and are not returned as tiles when querying the contents of the clock region.
        if { [llength ${cr_tiles}] > 0 } {
          # Get the min/max col index for the tiles in the clock region.
          lassign [get_clock_region_tile_col_boundaries ${clock_region}] min_tile_col_idx max_tile_col_idx

          # Iterate over the columns in the clock region in order.
          for {set tile_col_idx ${min_tile_col_idx}} {${tile_col_idx} <= ${max_tile_col_idx}} {incr tile_col_idx} {
            # Tiles at the given column.
            # Note that we use "-quiet" as we know some columns contain no tiles (and hence no sites).
            # Vivado emts a warning for every such column it encounters and this gives
            # the impression something is wrong. However, we handle this case explicitly
            # in what follows, so we use "quiet" here to remove the warning.
            set tiles [get_tiles -quiet -of_objects ${clock_region} -filter "COLUMN == ${tile_col_idx}"]

            # Keep sites that correspond to DSPs. We again use -quiet to avoid warnings
            # since we explicitly handle the case where there are no bels below.
            set sites [get_sites -quiet -of_objects ${tiles} -regexp ${dsp_site_pattern}]

            if { [llength ${sites}] > 0 } {
              # Select the site with the smallest Y coordinate. We can sort the sites and select
              # the first one using `lsort -dictionary {list}` as all sites have names like "DSP48E2_X(\d+)Y(\d+)/([ABCDEFGH]FF2?)"
              # and the X coordinate is identical between all entries (they are in the same column). The
              # entries will therefore be sorted by their Y-value.
              set sites_sorted [lsort -dictionary ${sites}]
              set num_sites [llength ${sites_sorted}]
              set min_site [lindex ${sites_sorted} 0]
              set max_site [lindex ${sites_sorted} [expr ${num_sites} - 1]]
              puts "Processing (SLR, major_row, dsp_min, dsp_max) sites (${slr}, ${cr_row_idx}, ${min_site}, ${max_site})"

              # Keep track of the DSP. Note that we use a row major that is RELATIVE to the SLR.
              lappend saved_dsp_locs [list ${slr} ${cr_row_idx} ${min_site} ${max_site}]
            }; # non-empty sites
          }; # clock region tile column idx
        }; # clock region empty?
      }; # clock region col idx
    }; # clock region row idx
  }; # SLR

  return ${saved_dsp_locs}
}

proc main { fpga_part bitstream_out_name dsp_out_name } {
  # We create an in-memory project to avoid having something written to disk at the current working directory.
  create_project "one_dsp_in_every_clb_column" -in_memory -part ${fpga_part}
  # We create an "I/O Planning Project" so we don't need to run implementation to be able to open the device for inspection.
  set_property DESIGN_MODE PinPlanning [current_fileset]
  # Many commands below only work on an open design.
  open_io_design -name io_1

  # We first need to know how many DSPs to instantiate. This is why we used an "I/O Planning Project" as it
  # allows us to open the device for inspection. The normal "RTL" mode does not let us do this without synthesizing a
  # design first to have a design we can "open"

  # Each entry is a (slr, clock region row index, bottom col DSP, top col DSP).
  # We will only instantiate the bottom DSP though (later down when doing `place_cell`). Since the entries are lists,
  # the cardinality of dsp_locs is the same as the number of bottom-most DSPs we want to instantiate. We do NOT need to
  # divide num_dsps below by 2.
  set dsp_locs [get_candidate_dsps]
  set num_dsps [llength ${dsp_locs}]

  # Write list of DSPs to file.
  set file_out [open ${dsp_out_name} w]
  puts ${file_out} [format_json [tcl_to_json ${dsp_locs}]]
  close ${file_out}

  puts "Instantiating ${num_dsps} DSPs (one per DSP column)"

  set_property DESIGN_MODE RTL [current_fileset]

  # Synthesize a replicated DSP design described in a verilog file. Note that `synth_design` will
  # automatically cause the project to transition to a standard "RTL" kernel again.
  # We also don't care about timing at all in this design, so we disable timing-driven synthesis entirely.
  read_verilog $::script_path/dsp.v
  synth_design -top dsp -no_timing_driven -generic G_SIZE=${num_dsps}

  # Note that this design does not require an XDC file as nothing is connected to FPGA pins.

  # Place all DSPs at the locations we computed before synthesis.
  foreach idx [struct::list iota ${num_dsps}] dsp_loc_pair_info ${dsp_locs} {
    # (SLR, major_row, dsp_min, dsp_max)
    set dsp_bottom_loc [lindex ${dsp_loc_pair_info} 2]
    set dsp_top_loc [lindex ${dsp_loc_pair_info} 3]
    # The name we query here is the name used in the verilog file.
    set dsp_bottom_cell [get_cells "DSP48E2_gen[${idx}].DSP48E2_inst"]
    place_cell ${dsp_bottom_cell} ${dsp_bottom_loc}
  }

  # # Optimizing the design is not really needed as it is somewhat performed by `synth_design`.
  # opt_design
  place_design
  route_design

  set checkpoint_out_name [replace_file_extension ${bitstream_out_name} "dcp"]
  write_checkpoint -force ${checkpoint_out_name}

  # # Debug
  # start_gui

  # Boards with HBM (like the U50) have a catastrophic trip (CATTRIP) port which
  # is supposed to be explicitly driven. If not driven, a DRC check fails and we
  # cannot generate a bitstream. This CATTRIP port is responsible for shutting
  # down the FPGA's power rails if the HBM reaches a critical temperature to
  # avoid damaging the card. Evan an empty bitstream for a HBM-enabled device
  # needs to have the CATTRIP port driven,
  # However, we do not want to use an XDC file in this TCL script to make it
  # work with all possible parts without requiring users to somehow find a XDC
  # file for each one. We therefore disable the DRC. This is safe as we are not
  # programming any device with this bitstream anyways.
  set_property IS_ENABLED 0 [get_drc_checks {PPURQ-1}]

  # Generate the bitstream.
  set_property BITSTREAM.GENERAL.COMPRESS FALSE     [current_design]
  set_property BITSTREAM.GENERAL.CRC DISABLE        [current_design]
  write_bitstream -force ${bitstream_out_name}
}

# We test the length of $::argv instead of just checking $::argc as $::argc
# contains the count of args BEFORE options parsing. Options parsing removes
# optional args and the length of $::argv is the only way to get an accurate
# count of the mandatory args that are left behind.
if { [llength $::argv] != 3 } {
  puts "received mandatory args: $::argv"
  puts "expected mandatory args: <fpga_part> <bitstream_out> <dsp_out>"
} else {
  set fpga_part [lindex $::argv 0]
  set bitstream_out [lindex $::argv 1]
  set dsp_out [lindex $::argv 2]
  main ${fpga_part} ${bitstream_out} ${dsp_out}
}
