# author: Sahand Kashani <sahand.kashani@epfl.ch>

# To call this script, use the following command:
#
#   vivado -mode batch -source extract_device_info.tcl -notrace -tclargs <fpga_part> <json_out>
#
# Example:
#
#   vivado -mode batch -source extract_device_info.tcl -notrace -tclargs xcu250-figd2104-2L-e output.json
#
# The output of this script is a single file defined by the <json_out> argument.

source [file join [file dirname [info script]] helpers.tcl]

proc emit_properties { object } {
  set lines {}

  foreach property_name [list_property ${object}] {
    set property_value [get_property ${property_name} ${object}]
    # We don't know if the property is a string or a list, so we use the generic `tcl_to_json`
    # function here as it can handle both types.
    lappend lines "\"${property_name}\": [tcl_to_json ${property_value}]"
  }

  return "\{[join ${lines} ","]\}"
}

proc emit_tileType_siteType_pairs { } {
  set tileType_siteType_pairs {}

  foreach site [get_sites] {
    set tile [get_tiles -quiet -of_objects ${site}]
    set site_type [get_property SITE_TYPE ${site}]
    set tile_type [get_property TILE_TYPE ${tile}]
    lappend tileType_siteType_pairs [list ${tile_type} ${site_type}]
  }

  set uniq [uniquify_list ${tileType_siteType_pairs}]
  return [tcl_list_to_json_list [lsort -dictionary ${uniq}]]
}

# Extracts a json string representation of the tiles and sites in the given column. The result looks like:
#
#   {
#      <tile_name_1>: [ <sites_in_tile_1> ],
#      <tile_name_2>: [ <sites_in_tile_2> ],
#      ...
#   }
#
# If no tiles exist in the column, then an empty json object "{}" is returned.
proc emit_tile_col { clock_region col_idx } {
  set lines {}

  # Tiles at the given column.
  # Note that we use "-quiet" as we know some columns contain no tiles.
  # Vivado emts a warning for every such column it encounters and this gives
  # the impression something is wrong. However, we handle this case explicitly
  # in what follows, so we use "quiet" here to remove the warning.
  # Note that sorting is not really necessary here and I only do it to have
  # an output that is easier to read.
  set tiles [lsort -dictionary [get_tiles -quiet -of_objects ${clock_region} -filter "COLUMN == ${col_idx}"]]
  if { [llength ${tiles}] > 0 } {
    foreach tile ${tiles} {
      # Enumerate all SITEs at the candidate tile. UG912 pg 133 (Tile) says:
      #
      #   A TILE is a device object containing ONE OR MORE SITE objects.
      #
      # However, in reality there are some tiles that do not contain any sites ("LAG_LAG" tiles for
      # example), hence why we explicitly check the size of ${sites} below as well.
      # Since there may be no sites in the given tile, we use "-quiet" to avoid an error.
      # Note that sorting is not really necessary here and I only do it to have
      # an output that is easier to read.
      set sites [lsort -dictionary [get_sites -quiet -of_objects ${tile}]]
      # I always want a list for ${sites}, hence why I explicitly use `tcl_list_to_json_list`
      # instead of calling `tcl_to_json`.
      lappend lines "\"${tile}\": [tcl_list_to_json_list ${sites}]"
    }
  }

  return "\{[join ${lines} ","]\}"
}

# Goes over the given tile columns in the clock region and creates a string
# representation of each column's details.
# If none of the columns have any tiles, then an empty json object "{}" is returned.
proc emit_tile_cols { clock_region min_col_idx max_col_idx } {
  set lines {}

  # Iterate over the clock region's columns in order.
  for {set col_idx ${min_col_idx}} {${col_idx} <= ${max_col_idx}} {incr col_idx} {
    # puts "Processing clock region ${clock_region}, col_idx = ${col_idx}"
    set col_info_str [emit_tile_col ${clock_region} ${col_idx}]
    # Only emit a tile column if it is non-empty as otherwise it pollutes the output.
    if { ${col_info_str} != "{}" } {
      lappend lines "\"${col_idx}\": ${col_info_str}"
    }
  }

  return "\{[join ${lines} ","]\}"
}

proc emit_clock_region { clock_region } {
  set lines {}

  set tiles [get_tiles -quiet -of_objects ${clock_region}]

  # Some clock regions could have nothing inside them. This often happens in Zynq devices as
  # some clock regions are taken up by hard processors. These processors are not visible in the
  # floorplan and are not returned as tiles when querying the contents of the clock region.
  if { [llength ${tiles}] > 0 } {
    # Get the min/max col index for the tiles in the clock region.
    lassign [get_clock_region_tile_col_boundaries ${clock_region}] min_cr_tile_col_idx max_cr_tile_col_idx

    lappend lines "\"num_tile_cols\": [expr ${max_cr_tile_col_idx} - ${min_cr_tile_col_idx} + 1]"
    lappend lines "\"min_tile_col_idx\": ${min_cr_tile_col_idx}"
    lappend lines "\"max_tile_col_idx\": ${max_cr_tile_col_idx}"
    lappend lines "\"tile_cols\": [emit_tile_cols ${clock_region} ${min_cr_tile_col_idx} ${max_cr_tile_col_idx}]"
  }

  return "\{[join ${lines} ","]\}"
}

proc emit_slr { slr } {
  set lines {}

  # Get the min/max col/row index for the clock regions ("cr") in the current SLR.
  # Clock regions are the large tiles of the form "X(\d+)Y(\d+)".
  lassign [get_slr_clock_region_boundaries ${slr}] min_cr_col_idx max_cr_col_idx min_cr_row_idx max_cr_row_idx
  lappend lines "\"slr_idx\": [get_property SLR_INDEX ${slr}]"
  lappend lines "\"config_order_idx\": [get_property CONFIG_ORDER_INDEX ${slr}]"
  lappend lines "\"num_clock_regions\": [expr (${max_cr_col_idx} - ${min_cr_col_idx} + 1) * (${max_cr_row_idx} - ${min_cr_row_idx} + 1)]"
  lappend lines "\"min_clock_region_col_idx\": ${min_cr_col_idx}"
  lappend lines "\"max_clock_region_col_idx\": ${max_cr_col_idx}"
  lappend lines "\"min_clock_region_row_idx\": ${min_cr_row_idx}"
  lappend lines "\"max_clock_region_row_idx\": ${max_cr_row_idx}"

  set clock_regions_lines {}

  # Iterate over the clock regions of the SLR in order.
  for {set cr_row_idx ${min_cr_row_idx}} {${cr_row_idx} <= ${max_cr_row_idx}} {incr cr_row_idx} {
    for {set cr_col_idx ${min_cr_col_idx}} {${cr_col_idx} <= ${max_cr_col_idx}} {incr cr_col_idx} {
      # This is the current clock region we must enumerate the properties of.
      set clock_region [get_clock_regions -of_objects ${slr} X${cr_col_idx}Y${cr_row_idx}]

      puts "Processing clock region ${clock_region}"
      lappend clock_regions_lines "\"${clock_region}\": [emit_clock_region ${clock_region}]"
    }
  }

  set clock_regions_str "\{[join ${clock_regions_lines} ","]\}"
  lappend lines "\"clock_regions\": ${clock_regions_str}"

  return "\{[join ${lines} ","]\}"
}

proc emit_slrs { } {
  set lines {}

  set slrs_lines {}
  # Get the min/max SLR indices.
  lassign [get_slr_index_boundaries] min_slr_idx max_slr_idx
  # Iterate over SLRs in order.
  for {set slr_idx ${min_slr_idx}} {${slr_idx} <= ${max_slr_idx}} {incr slr_idx} {
    set slr [get_slrs -filter "SLR_INDEX == ${slr_idx}"]
    lappend slrs_lines "\"${slr}\": [emit_slr ${slr}]"
  }
  set slrs_str "\{[join ${slrs_lines} ","]\}"

  lappend lines "\"num_slrs\": [llength [get_slrs]]"
  lappend lines "\"slrs\": ${slrs_str}"

  return "\{[join ${lines} ","]\}"
}

proc main { fpga_part json_out } {
  # We create an in-memory project to avoid having something written to disk at the current working directory.
  create_project "extract_device_info" -in_memory -part ${fpga_part}
  # We create an "I/O Planning Project" so we don't need to run implementation to be able to open the device for inspection.
  set_property DESIGN_MODE PinPlanning [current_fileset]
  # Many commands below (like "get_slrs") only work on an open design.
  open_io_design -name io_1

  set lines {}
  lappend lines "\"part_properties\": [emit_properties [get_parts ${fpga_part}]]"
  lappend lines "\"tileType_siteType_pairs\": [emit_tileType_siteType_pairs]"
  lappend lines "\"composition\": [emit_slrs]"
  set json_str "\{[join ${lines} ","]\}"

  set file_out [open ${json_out} w]
  puts ${file_out} [format_json ${json_str}]
  close ${file_out}
}

# We test the length of $::argv instead of just checking $::argc as $::argc
# contains the count of args BEFORE options parsing. Options parsing removes
# optional args and the length of $::argv is the only way to get an accurate
# count of the mandatory args that are left behind.
if { [llength $::argv] != 2 } {
  puts "received mandatory args: $::argv"
  puts "expected mandatory args: <fpga_part> <json_out>"
} else {
  set fpga_part [lindex $::argv 0]
  set json_out [lindex $::argv 1]
  main ${fpga_part} ${json_out}
}
