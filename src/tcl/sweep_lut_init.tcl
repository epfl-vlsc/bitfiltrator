# author: Sahand Kashani <sahand.kashani@epfl.ch>

# To call this script, use the following command:
#
#   vivado -mode batch -source sweep_lut_init.tcl -notrace -tclargs <dcp_in> <lut_idx_low> <lut_idx_high> <dir_out>
#
# Example:
#
#   vivado -mode batch -source sweep_lut_init.tcl -notrace -tclargs xcu250-figd2104-2L-e.dcp 0 10 ./
#
# The outputs of this script are multiple files in <dir_out> with the format:
#   - <dir_out>/lut_gen[<lut_idx>].lut6_inst_b<lut_init>.bit.gz
#   - <dir_out>/lut_gen[<lut_idx>].lut6_inst_b<lut_init>.dcp
#
# Note that the output bitstreams are compressed to save a significant amount of disk space given
# the large search space.

package require struct::list

source [file join [file dirname [info script]] helpers.tcl]

set script_path [file dirname [file normalize [info script]]]

# Selects luts of the form "lut_gen\[(\d+)\]\.lut6_inst" where the (\d+) capture
# group is between ${idx_low} and ${idx_high}.
proc get_luts { idx_low idx_high } {
  set luts {}

  set lut_pattern "lut_gen\\\[(\\d+)\\\]\.lut6_inst"

  foreach cell [get_cells -regexp ${lut_pattern}] {
    # The "-" below is because regexp returns the full match first, then the groups
    # in the regular expression. I don't care about the full match, hence the "-"
    # to ignore the return value.
    regexp ${lut_pattern} ${cell} - idx
    if { [expr ${idx_low} <= ${idx}] && [expr ${idx} <= ${idx_high}] } {
      lappend luts ${cell}
    }
  }

  return [lsort -dictionary ${luts}]
}

proc main { dcp_in lut_idx_low lut_idx_high dir_out } {
  open_checkpoint ${dcp_in}

  set luts [get_luts ${lut_idx_low} ${lut_idx_high}]
  puts "Handling equation sweep for LUTs ${luts}"

  # This design contains combinational loops and we have to explicitly mark them
  # as desired to avoid a DRC error. We just mark all nets as being possibly
  # combinational.
  set_property ALLOW_COMBINATORIAL_LOOPS TRUE [get_nets]

  # General bitstream settings
  set_property BITSTREAM.GENERAL.COMPRESS FALSE     [current_design]
  set_property BITSTREAM.GENERAL.CRC DISABLE        [current_design]

  foreach lut ${luts} {
    foreach idx [struct::list iota 64] {
      set equation_bin [one_hot_bin_str 64 ${idx}]
      set_property INIT 64'b${equation_bin} ${lut}

      set bitstream_out_name ${dir_out}/${lut}_b${equation_bin}.bit
      set checkpoint_out_name [replace_file_extension ${bitstream_out_name} "dcp"]
      # puts ${bitstream_out_name}
      # puts ${checkpoint_out_name}

      write_checkpoint -force ${checkpoint_out_name}
      write_bitstream -force ${bitstream_out_name}

      # Compress the bitstream to save disk space. The original .bit file is
      # automatically deleted.
      exec gzip -f ${bitstream_out_name}
    }

    # Reset the lut's equation to 0 to ensure the next lut is the only one with a bit set.
    set_property INIT "64'h0000000000000000" ${lut}
  }
}

# We test the length of $::argv instead of just checking $::argc as $::argc
# contains the count of args BEFORE options parsing. Options parsing removes
# optional args and the length of $::argv is the only way to get an accurate
# count of the mandatory args that are left behind.
if { [llength $::argv] != 4 } {
  puts "received mandatory args: $::argv"
  puts "expected mandatory args: <dcp_in> <lut_idx_low> <lut_idx_high> <dir_out>"
} else {
  set dcp_in [lindex $::argv 0]
  set lut_idx_low [lindex $::argv 1]
  set lut_idx_high [lindex $::argv 2]
  set dir_out [lindex $::argv 3]
  main ${dcp_in} ${lut_idx_low} ${lut_idx_high} ${dir_out}
}
