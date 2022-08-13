# author: Sahand Kashani <sahand.kashani@epfl.ch>

# To call this script, use the following command:
#
#   vivado -mode batch -source one_bram_in_every_clb_column.tcl -notrace -tclargs <fpga_part> <bitstream_out>
#
# Example:
#
#   vivado -mode batch -source one_bram_in_every_clb_column.tcl -notrace -tclargs xcu250-figd2104-2L-e output.bit
#
# The outputs of this script are 3 files:
#   - <bitstream_out>
#   - logic location file (using same prefix as <bitstream_out> with ".ll" extension)
#   - dcp file (using same prefix as <bitstream_out> with ".dcp" extension)

package require struct::list

source [file join [file dirname [info script]] helpers.tcl]

set script_path [file dirname [file normalize [info script]]]

# Enumerates all candidate BRAMs that should be used in the design IN ORDER. These BRAMs are the bottom-most
# BRAMs (RAMB18_X<x>Y<y>, where Y is the smallest in its clock region) in every BRAM column.
proc get_candidate_brams {} {
  puts "Enumerating BRAMs"

  # Empty list we will populate.
  set saved_bram_locs {}

  set bram18_site_pattern "RAMB18_X(\\d+)Y(\\d+)"

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

            # Keep sites that correspond to BRAMs. We again use -quiet to avoid warnings
            # since we explicitly handle the case where there are no sites below.
            set sites [get_sites -quiet -of_objects ${tiles} -regexp ${bram18_site_pattern}]

            if { [llength ${sites}] > 0 } {
              # Select the BRAM site with the smallest Y coordinate. We can sort the sites and select
              # the first one using `lsort -dictionary {list}` as all sites have names like "RAMB18_X(\d+)Y(\d+)/<bel>"
              # and the X coordinate is identical between all entries (they are in the same column). The entries will
              # therefore be sorted by their Y-value.
              set sites_sorted [lsort -dictionary ${sites}]
              set site [lindex ${sites_sorted} 0]
              # puts "Processing site ${site}"

              # Keep track of the BRAM BEL as the next element of the large BRAM ring we want to create.
              # Note that Vivado names the BELs obtained by running `[get_bels -of_objects ${site}]` for
              # a BRAM site as "RAMBFIFO18", not "RAMB18E2" or "FIFO18E2". This is wrong and we cannot use
              # the bel name "RAMBFIFO18" to successfully place a BRAM. Valid names I have found are
              # - FIFO18E2 (but only for the bottom 18K BRAM)
              # - RAMB18E2_L (when Y is an even number)
              # - RAMB18E2_U (when Y is an odd number)
              # I therefore manually place "RAMB18E2_L" after the "/" that separates the site name from
              # the BEL inside it as I couldn't get vivado to programmatically generate the correct names.
              # lappend saved_bram_locs "${site}/RAMB18E2_L"

              # Note that one should use a BEL when placing a cell, but you csn use a SITE if there is
              # only 1 way (i.e. 1 BEL) where the cell can be placed in the site. This is the case for
              # a 18K BRAM, so I just return the name of the site instead of that of a hard-coded BEL.
              lappend saved_bram_locs ${site}
            }; # non-empty sites
          }; # clock region tile column idx
        }; # clock region empty?
      }; # clock region col idx
    }; # clock region row idx
  }; # SLR

  return ${saved_bram_locs}
}

proc main { fpga_part bitstream_out_name } {
  # We create an in-memory project to avoid having something written to disk at the current working directory.
  create_project "one_bram_in_every_clb_column" -in_memory -part ${fpga_part}
  # We create an "I/O Planning Project" so we don't need to run implementation to be able to open the device for inspection.
  set_property DESIGN_MODE PinPlanning [current_fileset]
  # Many commands below only work on an open design.
  open_io_design -name io_1

  # We first need to know how wide the ring BRAM should be. This is why we used an "I/O Planning Project" as it
  # allows us to open the device for inspection. The normal "RTL" mode does not let us do this without synthesizing a
  # design first to have a design we can "open".
  set bram_sites [get_candidate_brams]
  set num_brams [llength ${bram_sites}]

  puts "Creating ring BRAM of size ${num_brams}"

  set_property DESIGN_MODE RTL [current_fileset]

  # Synthesize a ring BRAM design described in a verilog file. Note that `synth_design` will
  # automatically cause the project to transition to a standard "RTL" kernel again.
  # We don't care about timing at all in this design, so we disable timing-driven synthesis entirely.
  read_verilog $::script_path/ring_bram.v
  synth_design -top ring_bram -no_timing_driven -generic G_SIZE=${num_brams}

  # Note that this design does not require an XDC file as nothing is connected to FPGA pins.

  # Place all BRAMs at the locations we computed before synthesis.
  foreach idx [struct::list iota ${num_brams}] bram_loc ${bram_sites} {
    # The name we query here is the name used in the verilog file.
    set bram_cell [get_cells "bram_gen[${idx}].RAMB18E2_inst"]
    # Note that bram_loc is a SITE, not a BEL. However, the site we have chosen can accomodate
    # our cell in only 1 way, so we let Vivado choose this configuration automatically (unlike
    # for SLICEs where a register could be placed in multiple places and we need to specify
    # which one we want explicitly).
    place_cell ${bram_cell} ${bram_loc}
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
