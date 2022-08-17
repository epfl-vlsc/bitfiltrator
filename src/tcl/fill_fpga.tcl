# author: Sahand Kashani <sahand.kashani@epfl.ch>

# To call this script, use the following command:
#
#   vivado -mode batch -source fill_fpga.tcl -notrace -tclargs <fpga_part> <dcp_out> <design_info_json_out>
#
# Example:
#
#   vivado -mode batch -source fill_fpga.tcl -notrace -tclargs xcu250-figd2104-2L-e output.dcp output.json
#
# The outputs of this script is 1 file:
#   - <dcp_out>
#   - <design_info_json_out>

package require struct::list

source [file join [file dirname [info script]] helpers.tcl]

set script_path [file dirname [file normalize [info script]]]

proc dump_lut_info { lut_cell } {
  set lines {}

  # Set random value for initial configuration.
  set_property "INIT" [rand_n_bit_verilog_number_str 64] ${lut_cell}

  # I use `get_bels` instead of `get_sites` as I want the trailing "/[A-H]6LUT"
  set lut_loc [get_bels -of_objects ${lut_cell}]
  lappend lines "\"loc\": \"${lut_loc}\""
  lappend lines "\"INIT\": \"[get_property INIT ${lut_cell}]\""
  return "\{[join ${lines} ","]\}"
}

proc dump_ff_info { ff_cell } {
  set lines {}

  # Set random value for initial configuration.
  set_property "INIT" [rand_n_bit_verilog_number_str 1] ${ff_cell}

  # I use `get_bels` instead of `get_sites` as I want the trailing "/[A-H]FF2?"
  set ff_loc [get_bels -of_objects ${ff_cell}]
  lappend lines "\"loc\": \"${ff_loc}\""
  lappend lines "\"INIT\": \"[get_property INIT ${ff_cell}]\""
  return "\{[join ${lines} ","]\}"
}

proc dump_bram_parity_info { bram_cell } {
  set lines {}

  foreach idx [struct::list iota 8] {
    set property_name "INITP_[format %02x ${idx}]"

    # Set random value for initial configuration.
    set_property ${property_name} [rand_n_bit_verilog_number_str 256] ${bram_cell}

    set property_value [get_property ${property_name} ${bram_cell}]
    lappend lines "\"${property_name}\": \"${property_value}\""
  }

  return "\{[join ${lines} ","]\}"
}

proc dump_bram_memory_info { bram_cell } {
  set lines {}

  foreach idx [struct::list iota 64] {
    set property_name "INIT_[format %02x ${idx}]"

    # Set random value for initial configuration.
    set_property ${property_name} [rand_n_bit_verilog_number_str 256] ${bram_cell}

    set property_value [get_property ${property_name} ${bram_cell}]
    lappend lines "\"${property_name}\": \"${property_value}\""
  }

  return "\{[join ${lines} ","]\}"
}

proc dump_bram_reg_info { bram_cell } {
  set lines {}

  foreach letter {A B} {
    set property_name "INIT_${letter}"

    # Set random value for initial configuration.
    set_property ${property_name} [rand_n_bit_verilog_number_str 18] ${bram_cell}

    set property_value [get_property ${property_name} ${bram_cell}]
    lappend lines "\"${property_name}\": \"${property_value}\""
  }

  return "\{[join ${lines} ","]\}"
}

proc dump_bram_info { bram_cell } {
  set lines {}

  set bram_loc [get_sites -quiet -of_objects ${bram_cell}]

  lappend lines "\"loc\": \"${bram_loc}\""
  lappend lines "\"parity\": [dump_bram_parity_info ${bram_cell}]"
  lappend lines "\"memory\": [dump_bram_memory_info ${bram_cell}]"
  lappend lines "\"register\": [dump_bram_reg_info ${bram_cell}]"

  return "\{[join ${lines} ","]\}"
}

proc dump_lut_infos { } {
  puts "Dumping lut information"

  set lut_cells [get_cells "slice_gen*.lut6_inst"]

  foreach lut_cell ${lut_cells} {
    lappend lines "\"${lut_cell}\": [dump_lut_info ${lut_cell}]"
  }

  return "\{[join ${lines} ","]\}"
}

proc dump_reg_infos { } {
  puts "Dumping register information"

  set ff_cells [get_cells "slice_gen*.ff_inst"]

  foreach ff_cell ${ff_cells} {
    lappend lines "\"${ff_cell}\": [dump_ff_info ${ff_cell}]"
  }

  return "\{[join ${lines} ","]\}"
}

proc dump_bram_infos { } {
  puts "Dumping bram information"

  set bram_cells [get_cells "bram_gen*"]

  foreach bram_cell ${bram_cells} {
    lappend lines "\"${bram_cell}\": [dump_bram_info ${bram_cell}]"
  }

  return "\{[join ${lines} ","]\}"
}

proc dump_design_info { } {
  puts "Dumping design information"

  set lines {}

  lappend lines "\"luts\": [dump_lut_infos]"
  lappend lines "\"regs\": [dump_reg_infos]"
  lappend lines "\"brams\": [dump_bram_infos]"

  return "\{[join ${lines} ","]\}"
}

proc main { fpga_part dcp_out design_info_json_out } {
  # We create an in-memory project to avoid having something written to disk at the current working directory.
  create_project "fill_fpga" -in_memory -part ${fpga_part}
  # We create an "I/O Planning Project" so we don't need to run implementation to be able to open the device for inspection.
  set_property DESIGN_MODE PinPlanning [current_fileset]
  # Many commands below only work on an open design.
  open_io_design -name io_1

  set part_info [get_parts ${fpga_part}]
  set num_regs [get_property "FLIPFLOPS" ${part_info}]
  set num_luts [get_property "LUT_ELEMENTS" ${part_info}]
  set num_brams [get_property "BLOCK_RAMS" ${part_info}]

  puts "Number of FFs   = ${num_regs}"
  puts "Number of LUTs  = ${num_luts}"
  puts "Number of BRAMs = ${num_brams}"

  # Do NOT go over all clock regions and enumerate the LUTs/FFs/BRAMs you want to use
  # in the design. The reason is doing so on some FPGAs will return MORE LUTS/FFs/BRAMs
  # than there are "in the device"!
  # Some devices like the xcau20p and xcau25p are identical in terms of number of
  # frames and of their type, but the number of brams they have differ (200 vs 300).
  # You can actually count 960 BRAMs in these devices when you check the floorplan as
  # there are 10 BRAM columns per major row, 24 18K BRAMs each, 4 major rows = 10 * 24 * 4 = 960.
  # Even if I assume the "BLOCK_RAMS" property above is the number of 36K BRAMS, that would
  # give us 10 * 12 * 4 = 480 BRAMs, not 200 or 300. So I the number of BRAMs you can
  # use it just limited by software and any of the 960 BRAMs are usable, so long as
  # you don't use more than the software-defined maximu.
  # Therefore we simply instantiate the maximum number of a given resource and let Vivado
  # deal with wherever it wants to place them.

  # If we populate all LUTs/FFs in the device, then Vivado doesn't finish P&R even after
  # multiple hours, so we just restrict the number of LUTs and Vivado will randomly place
  # the LUTs where it wants. We should in theory be able to instantiate all SLICEs in the
  # device (minus 1 from the software-defined limit because we use one FF as the "clock"
  # of the BRAM) on the device if we just waited long enough for Vivado to finish.
  set num_slices [expr ${num_luts} / 4]

  set_property DESIGN_MODE RTL [current_fileset]

  # Synthesize a design described in a verilog file. Note that `synth_design` will
  # automatically cause the project to transition to a standard "RTL" kernel again.
  # We also don't care about timing at all in this design, so we disable timing-driven
  # synthesis entirely.
  read_verilog $::script_path/fill_fpga.v
  set_param synth.elaboration.rodinMoreOptions "rt::set_parameter max_loop_limit 1000000"
  synth_design -top fill_fpga -no_timing_driven -generic G_NUM_SLICE=${num_slices} -generic G_NUM_BRAM=${num_brams}

  # Note that this design does not require an XDC file as nothing is connected to FPGA pins.

  # # Optimizing the design is not really needed as it is somewhat performed by `synth_design`.
  # opt_design
  place_design
  route_design

  # Randomize initial configuration of cells and dump to a JSON file.
  set json_str [dump_design_info]
  set file_out [open ${design_info_json_out} w]
  puts ${file_out} [format_json ${json_str}]
  close ${file_out}

  # Write the checkpoint after `dump_design_info` above as we set the initial configuration
  # of cells there and we need the checkpoint to reflect this new information.
  write_checkpoint -force ${dcp_out}
}

# We test the length of $::argv instead of just checking $::argc as $::argc
# contains the count of args BEFORE options parsing. Options parsing removes
# optional args and the length of $::argv is the only way to get an accurate
# count of the mandatory args that are left behind.
if { [llength $::argv] != 3 } {
  puts "received mandatory args: $::argv"
  puts "expected mandatory args: <fpga_part> <dcp_out> <design_info_json_out>"
} else {
  set fpga_part [lindex $::argv 0]
  set dcp_out [lindex $::argv 1]
  set design_info_json_out [lindex $::argv 2]
  main ${fpga_part} ${dcp_out} ${design_info_json_out}
}
