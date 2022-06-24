# To call this script, use the following command:
#
#   vivado -mode batch -source empty_design.tcl -notrace -tclargs <fpga_part> <dcp_out>
#
# Example:
#
#   vivado -mode batch -source empty_design.tcl -notrace -tclargs xcu250-figd2104-2L-e output.dcp
#
# The output of this script are 2 files:
#   - <dcp_out>

package require struct::list

source [file join [file dirname [info script]] helpers.tcl]

set script_path [file dirname [file normalize [info script]]]

proc main { fpga_part dcp_out } {
  # We create an in-memory project to avoid having something written to disk at the current working directory.
  create_project "empty_design" -in_memory -part ${fpga_part}

  # The empty_design.v file is a design with a single FDRE
  read_verilog $::script_path/empty_design.v
  synth_design -top empty_design -no_srlextract -no_timing_driven

  # Note that this design does not require an XDC file as nothing is connected to FPGA pins.

  # # Optimizing the design is not really needed as it is somewhat performed by `synth_design`.
  # opt_design
  place_design
  route_design

  write_checkpoint -force ${dcp_out}

  # # Debug
  # start_gui
}

# We test the length of $::argv instead of just checking $::argc as $::argc
# contains the count of args BEFORE options parsing. Options parsing removes
# optional args and the length of $::argv is the only way to get an accurate
# count of the mandatory args that are left behind.
if { [llength $::argv] != 2 } {
  puts "received mandatory args: $::argv"
  puts "expected mandatory args: <fpga_part> <dcp_out>"
} else {
  set fpga_part [lindex $::argv 0]
  set dcp_out [lindex $::argv 1]
  main ${fpga_part} ${dcp_out}
}
