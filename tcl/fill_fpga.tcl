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
  # I use `get_bels` instead of `get_sites` as I want the trailing "/[A-H]6LUT"
  set lut_loc [get_bels -of_objects ${lut_cell}]
  lappend lines "\"loc\": \"${lut_loc}\""
  lappend lines "\"INIT\": \"[get_property INIT ${lut_cell}]\""
  return "\{[join ${lines} ","]\}"
}

proc dump_ff_info { ff_cell } {
  set lines {}
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
    set property_value [get_property ${property_name} ${bram_cell}]
    lappend lines "\"${property_name}\": \"${property_value}\""
  }

  return "\{[join ${lines} ","]\}"
}

proc dump_bram_memory_info { bram_cell } {
  set lines {}

  foreach idx [struct::list iota 64] {
    set property_name "INIT_[format %02x ${idx}]"
    set property_value [get_property ${property_name} ${bram_cell}]
    lappend lines "\"${property_name}\": \"${property_value}\""
  }

  return "\{[join ${lines} ","]\}"
}

proc dump_bram_reg_info { bram_cell } {
  set lines {}

  foreach letter {A B} {
    set property_name "INIT_${letter}"
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

  set slice_pattern "SLICE_X(\\d+)Y(\\d+)"
  set bram_pattern "RAMB18_X(\\d+)Y(\\d+)"

  set slices [lsort -dictionary [get_sites -quiet -regexp ${slice_pattern}]]
  set num_slices [llength ${slices}]

  # Only take half the BRAMs as vivado sometimes returns more BRAMs that actually
  # exist on the device. This only happens for a few devices though. Maybe a bug
  # in Vivado when it is working on restricted devices (devices which are the
  # same as larger ones, but where some parts are disabled)?
  set brams [lsort -dictionary [get_sites -quiet -regexp ${bram_pattern}]]
  set num_brams [expr [llength ${brams}] / 2]
  set brams [lrange ${brams} 0 ${num_brams}]
  set num_brams [llength ${brams}]

  puts "Number of slices = ${num_slices}"
  puts "Number of BRAMs = ${num_brams}"

  set_property DESIGN_MODE RTL [current_fileset]

  # Synthesize a design described in a verilog file. Note that `synth_design` will
  # automatically cause the project to transition to a standard "RTL" kernel again.
  # We also don't care about timing at all in this design, so we disable timing-driven
  # synthesis entirely.
  read_verilog $::script_path/fill_fpga.v
  set_param synth.elaboration.rodinMoreOptions "rt::set_parameter max_loop_limit 1000000"
  synth_design -top fill_fpga -no_timing_driven -generic G_NUM_SLICE=${num_slices} -generic G_NUM_BRAM=${num_brams}

  # Note that this design does not require an XDC file as nothing is connected to FPGA pins.

  # We populate a single LUT/FF per slice. Which of the ABCDEFGH lut/ff gets used
  # depends on the Y index of the slice.
  # This is done as otherwise Vivado never finishes P&R, even after multiple hours.
  set sliceY_to_letter [dict create 0 "A" 1 "B" 2 "C" 3 "D" 4 "E" 5 "F" 6 "G" 7 "H"]
  foreach slice ${slices} idx [struct::list iota ${num_slices}] {
    # The "-" below is because regexp returns the full match first, then the groups
    # in the regular expression. I don't care about the full match, hence the "-"
    # to ignore the return value.
    regexp "SLICE_X(\\d+)Y(\\d+)" ${slice} - x y
    set y_rel [expr ${y} % 8]
    set letter [dict get ${sliceY_to_letter} ${y_rel}]

    # The name we query here is the name used in the verilog file.
    set lut_cell [get_cells "slice_gen[${idx}].lut6_inst"]
    set ff_cell [get_cells "slice_gen[${idx}].ff_inst"]
    set lut_loc "${slice}/${letter}6LUT"
    set ff_loc "${slice}/${letter}FF"
    place_cell ${lut_cell} ${lut_loc}
    place_cell ${ff_cell} ${ff_loc}

    # Set random value for initial configuration.
    set_property "INIT" [rand_n_bit_verilog_number_str 64] ${lut_cell}
    set_property "INIT" [rand_n_bit_verilog_number_str 1] ${ff_cell}
  }

  foreach bram ${brams} idx [struct::list iota ${num_brams}] {
    set bram_cell [get_cells "bram_gen[${idx}].RAMB18E2_inst"]
    set bram_loc ${bram}
    place_cell ${bram_cell} ${bram_loc}

    # Set random value for initial configuration.
    foreach idx [struct::list iota 8] {
      set property_name "INITP_[format %02x ${idx}]"
      set_property ${property_name} [rand_n_bit_verilog_number_str 256] ${bram_cell}
    }
    foreach idx [struct::list iota 64] {
      set property_name "INIT_[format %02x ${idx}]"
      set_property ${property_name} [rand_n_bit_verilog_number_str 256] ${bram_cell}
    }
    foreach letter {A B} {
      set property_name "INIT_${letter}"
      set_property ${property_name} [rand_n_bit_verilog_number_str 18] ${bram_cell}
    }
  }

  # # Optimizing the design is not really needed as it is somewhat performed by `synth_design`.
  # opt_design
  place_design
  route_design

  write_checkpoint -force ${dcp_out}

  # Write cell configuration to a file so another file can look for equations/contents in
  # a bitstream.
  set json_str [dump_design_info]
  set file_out [open ${design_info_json_out} w]
  puts ${file_out} [format_json ${json_str}]
  close ${file_out}
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
