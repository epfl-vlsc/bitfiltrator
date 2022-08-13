# author: Sahand Kashani <sahand.kashani@epfl.ch>

# To call this script, use the following command:
#
#   vivado -mode batch -source gen_bitstream_from_dcp.tcl -notrace -tclargs [-per_frame_crc] <dcp_in> <bitstream_out>
#
# Example:
#
#   vivado -mode batch -source gen_bitstream_from_dcp.tcl -notrace -tclargs [-per_frame_crc] checkpoint.dcp output.bit
#
# The output of this script is 1 file:
#   - <bitstream_out>

package require struct::list

source [file join [file dirname [info script]] helpers.tcl]

set script_path [file dirname [file normalize [info script]]]

proc main { dcp_in bitstream_out per_frame_crc } {
  open_checkpoint ${dcp_in}

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
  # We want this script to work for any FPGA.

  # Zynq devices do not support encryption. The default is "NO" for standard
  # FPGAs, so we don't need to explicitly set this property for this tcl file
  # to work with all devices.
  #
  # set_property BITSTREAM.ENCRYPTION.ENCRYPT NO      [current_design]

  set_property BITSTREAM.GENERAL.COMPRESS FALSE     [current_design]
  set_property BITSTREAM.GENERAL.CRC DISABLE        [current_design]

  if { ${per_frame_crc} } {
    set_property BITSTREAM.GENERAL.CRC ENABLE      [current_design]
    set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]
  }

  write_bitstream -force ${bitstream_out}
}

set cli_options {
  { "per_frame_crc" "Generate a bitstream with per-frame CRC" }
}
set cli_usage ": gen_bitstream_from_dcp \[options\] <dcp_in> <bitstream_out> \noptions:"

# Note that `cmdline::getoptions` will *modify* `::argv`, hence why we use the
# name of the variable `::argv` instead of dereferencing it with `$::argv`.
if { [catch { array set options [cmdline::getoptions ::argv ${cli_options} ${cli_usage}] }] } {
  # Note: argv is modified now. The recognized options are removed from it and
  # only the non-option arguments are left behind.
  puts [cmdline::usage ${cli_options} ${cli_usage}]
  exit 1
}

# We test the length of $::argv instead of just checking $::argc as $::argc
# contains the count of args BEFORE options parsing. Options parsing removes
# optional args and the length of $::argv is the only way to get an accurate
# count of the mandatory args that are left behind.
if { [llength $::argv] != 2 } {
  puts "received mandatory args: $::argv"
  puts "expected mandatory args: <dcp_in> <bitstream_out>"
} else {
  set dcp_in [lindex $::argv 0]
  set bitstream_out [lindex $::argv 1]

  main ${dcp_in} ${bitstream_out} $options(per_frame_crc)
}
