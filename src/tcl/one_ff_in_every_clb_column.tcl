# author: Sahand Kashani <sahand.kashani@epfl.ch>

# To call this script, use the following command:
#
#   vivado -mode batch -source one_ff_in_every_clb_column.tcl -notrace -tclargs <fpga_part> <bitstream_out>
#
# Example:
#
#   vivado -mode batch -source one_ff_in_every_clb_column.tcl -notrace -tclargs xcu250-figd2104-2L-e output.bit
#
# The outputs of this script are 3 files:
#   - <bitstream_out>
#   - logic location file (using same prefix as <bitstream_out> with ".ll" extension)
#   - dcp file (using same prefix as <bitstream_out> with ".dcp" extension)

package require struct::list

source [file join [file dirname [info script]] helpers.tcl]

set script_path [file dirname [file normalize [info script]]]

# Enumerates all candidate registers that should be used in the design IN ORDER. These registers are the bottom-most
# register (AFF) in the bottom-most SLICE of every CLB column.
proc get_candidate_regs {} {
  puts "Enumerating registers"

  # Empty list we will populate.
  set saved_reg_locs {}

  set reg_site_pattern "SLICE_X(\\d+)Y(\\d+)"
  set reg_bel_pattern "${reg_site_pattern}/(\[ABCDEFGH\]FF2?)"

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

            # Keep bels that correspond to SLICEs. We again use -quiet to avoid warnings
            # since we explicitly handle the case where there are no bels below.
            set bels [get_bels -quiet -of_objects ${tiles} -regexp ${reg_bel_pattern}]

            if { [llength ${bels}] > 0 } {
              # Select the reg bel with the smallest Y coordinate. We can sort the bels and select
              # the first one using `lsort -dictionary {list}` as all bels have names like "SLICE_X(\d+)Y(\d+)/([ABCDEFGH]FF2?)"
              # and the X coordinate is identical between all entries (they are in the same column). The
              # entries will therefore be sorted by their Y-value.
              set bels_sorted [lsort -dictionary ${bels}]
              set bel [lindex ${bels_sorted} 0]
              # puts "Processing bel ${bel}"

              # Keep track of the register as the next element of the large ring register we want to create.
              lappend saved_reg_locs ${bel}
            }; # non-empty bels
          }; # clock region tile column idx
        }; # clock region empty?
      }; # clock region col idx
    }; # clock region row idx
  }; # SLR

  return ${saved_reg_locs}
}

proc main { fpga_part bitstream_out_name } {
  # We create an in-memory project to avoid having something written to disk at the current working directory.
  create_project "one_ff_in_every_clb_column" -in_memory -part ${fpga_part}
  # We create an "I/O Planning Project" so we don't need to run implementation to be able to open the device for inspection.
  set_property DESIGN_MODE PinPlanning [current_fileset]
  # Many commands below only work on an open design.
  open_io_design -name io_1

  # We first need to know how wide the ring register should be. This is why we used an "I/O Planning Project" as it
  # allows us to open the device for inspection. The normal "RTL" mode does not let us do this without synthesizing a
  # design first to have a design we can "open".
  set reg_locs [get_candidate_regs]
  set num_regs [llength ${reg_locs}]

  puts "Creating ring register of size ${num_regs}"

  set_property DESIGN_MODE RTL [current_fileset]

  # Synthesize a ring register design described in a verilog file. Note that `synth_design` will
  # automatically cause the project to transition to a standard "RTL" kernel again.
  # Though the design itself marks the FDRE cells as DONT_TOUCH, as an extra security we instruct
  # vivado not to infer SRL-based shift registers. We also don't care about timing at all in this
  # design, so we disable timing-driven synthesis entirely.
  read_verilog $::script_path/ring_reg.v
  synth_design -top ring_reg -no_srlextract -no_timing_driven -generic G_SIZE=${num_regs}

  # Note that this design does not require an XDC file as nothing is connected to FPGA pins.

  # Place all registers at the locations we computed before synthesis.
  foreach idx [struct::list iota ${num_regs}] reg_loc ${reg_locs} {
    # The name we query here is the name used in the verilog file.
    set reg_cell [get_cells "FDRE_gen[${idx}].FDRE_inst"]
    place_cell ${reg_cell} ${reg_loc}
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
  write_bitstream -force -logic_location_file ${bitstream_out_name}
}

# We test the length of $::argv instead of just checking $::argc as $::argc
# contains the count of args BEFORE options parsing. Options parsing removes
# optional args and the length of $::argv is the only way to get an accurate
# count of the mandatory args that are left behind.
if { [llength $::argv] != 2 } {
  puts "received mandatory args: $::argv"
  puts "expected mandatory args: <fpga_part> <bitstream_out>"
} else {
  set fpga_part [lindex $::argv 0]
  set bitstream_out [lindex $::argv 1]
  main ${fpga_part} ${bitstream_out}
}
