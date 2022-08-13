# author: Sahand Kashani <sahand.kashani@epfl.ch>

# Returns the min/max SLR indices.
proc get_slr_index_boundaries { } {
  set slrs [get_slrs]
  set slr_min_idx [get_property -min SLR_INDEX ${slrs}]
  set slr_max_idx [get_property -max SLR_INDEX ${slrs}]
  return [list ${slr_min_idx} ${slr_max_idx}]
}

# Returns the min/max clock region row/col indices of the SLR.
# For example, if the SLR has clock regions {X0Y0, X1Y0, X2Y0, X0Y1, X1Y1, X2Y1},
# then this function returns {0, 2, 0, 1}.
#                             ^^^^  ^^^^
#                             col   row
proc get_slr_clock_region_boundaries { slr } {
  set clock_regions [get_clock_regions -of_objects ${slr}]

  # Each clock region is of the form "X(\d+)Y(\d+)"
  set col_indices [get_property COLUMN_INDEX ${clock_regions}]
  set row_indices [get_property ROW_INDEX ${clock_regions}]

  # You can technically use the "-min" or "-max" arg to `get_property` above
  # to find the corresponding value, but I explicitly store the full list
  # of indices for clarity.

  # The min/max functions in TCL do not operate on a list, but on a sequence
  # of values directly given as arguments. The "{*}" below unpacks the contents
  # of the list to its right.
  set min_col_idx [tcl::mathfunc::min {*}${col_indices}]
  set max_col_idx [tcl::mathfunc::max {*}${col_indices}]
  set min_row_idx [tcl::mathfunc::min {*}${row_indices}]
  set max_row_idx [tcl::mathfunc::max {*}${row_indices}]

  return [list ${min_col_idx} ${max_col_idx} ${min_row_idx} ${max_row_idx}]
}

# Returns the min/max tile column indices in the given clock region.
# For example, if the clock region has tiles starting from column index 49 to 120,
# then these numbers are returned.
proc get_clock_region_tile_col_boundaries { clock_region } {
  # Each clock region has a "TOP_LEFT_TILE" and "BOTTOM_RIGHT_TILE" property, but
  # unfortunately the "BOTTOM_RIGHT_TILE" property is always of the form
  # "NULL_X(\d+)Y(\d+)" and no tile with that name exists if you query it. So
  # you can't use these 2 tile names as the boundary tiles.

  # Instead, we enumerate all tiles in the clock region (since [get_tiles] does
  # not return the "NULL*" tile) and get their "COLUMN" property for every element
  # in the list.
  set tiles [get_tiles -quiet -of_objects ${clock_region}]
  set col_indices [get_property COLUMN ${tiles}]

  # The min/max functions in TCL do not operate on a list, but on a sequence
  # of values directly given as arguments. The "{*}" below unpacks the contents
  # of the list to its right.
  set min_col_idx [tcl::mathfunc::min {*}${col_indices}]
  set max_col_idx [tcl::mathfunc::max {*}${col_indices}]

  return [list ${min_col_idx} ${max_col_idx}]
}

# Gets the most common object in `objects` that has the given property.
proc get_most_common_object_with_property { objects property } {
  # `get_property` expects at least 1 object. This function will crash if called
  # with an empty object list.
  set types [get_property ${property} ${objects}]

  # Populate histogram.
  set hist [dict create]
  foreach type ${types} {
    dict incr hist ${type}
  }

  set max_type [lindex ${types} 0]
  set max_count -1
  dict for {type count} ${hist} {
    # puts "${type} ${count}"
    if {${count} > ${max_count}} {
      set max_type ${type}
      set max_count ${count}
    }
  }

  return ${max_type}
}

# Replaces a file extension in a name with a new extension.
proc replace_file_extension { fname new_ext } {
  set dir [file dirname ${fname}]
  set fname_without_ext [file rootname [file tail ${fname}]]
  set new_file_name "${dir}/${fname_without_ext}.${new_ext}"
  return ${new_file_name}
}

# Returns the device corresponding to a part number. All FPGAs with the same
# "DEVICE" property share the same internal topology. All that differs is their
# speed grade, package, etc.
proc get_device { fpga_part_name } {
  set part [get_parts ${fpga_part_name}]
  set device [get_property DEVICE ${part}]
  return ${device}
}

# Returns the unique elements in the list. Preserves the order of the elements
# in the original list. Taken from:
# https://wiki.tcl-lang.org/page/Unique+Element+List
proc uniquify_list { l } {
  set d {}
  foreach item ${l} {
    dict set d ${item} ""
  }
  return [dict keys ${d}]
}

# Enumerates all tiles in the first column that contains tiles with the
# given TILE_TYPE. This function searches for tile columns in the
# following order (SLR, row, col).
# Returns a list with:
# - target SLR index
# - target clock region row index
# - target clock region col index
# - target tile column index
# - target tiles
# If no tile column exists with the given requirements, then {-1 -1 -1 -1 {}} is returned.
proc get_first_col_with_tileType { tile_type { start_slr_idx 0 } { start_cr_row_idx 0 } { start_cr_col_idx 0 } { start_tile_col_idx 0 } } {
  puts "Searching for tile column of type ${tile_type}"
  puts "Search starting from SLR ${start_slr_idx}, clock region row ${start_cr_row_idx}, clock region col ${start_cr_col_idx}, tile col ${start_tile_col_idx}"

  # The very first iteration of the search must use the indices provided by the
  # caller. The subsequent iterations must use the appropriate min/max boundaries
  # of the (SLR / clock region / tile column) boundaries.
  set is_first_iteration 1

  # Get the min/max SLR indices.
  lassign [get_slr_index_boundaries] min_slr_idx max_slr_idx

  # Iterate over SLRs in order.
  for {set slr_idx ${start_slr_idx}} {${slr_idx} <= ${max_slr_idx}} {incr slr_idx} {
    set slr [get_slrs -filter "SLR_INDEX == ${slr_idx}"]
    # puts "Processing SLR ${slr}"

    # We want to iterate over the clock regions of the SLR in order. One might think an easy way of
    # doing this is to just call `lsort -dictionary [get_clock_regions -of_objects ${slr}]`, but
    # this is false. The command above would iterate over the clock regions in column order
    # {X0Y0, X0Y1, X0Y2, ..., X1Y0, ...}, whereas we want to iterate over the clock regions in row order
    # {X0Y0, X1Y0, X2Y0, ..., X0Y1, ...}.
    # We therefore resort to manual indexing to select the clock region of interest.

    # Get the min/max col/row index for the clock regions ("cr") in the current SLR.
    # Clock regions are the large tiles of the form "X(\d+)Y(\d+)".
    lassign [get_slr_clock_region_boundaries ${slr}] min_cr_col_idx max_cr_col_idx min_cr_row_idx max_cr_row_idx

    if { ! ${is_first_iteration} } {
      set start_cr_row_idx ${min_cr_row_idx}
    }

    # Iterate over the clock regions of the SLR in order.
    for {set cr_row_idx ${start_cr_row_idx}} {${cr_row_idx} <= ${max_cr_row_idx}} {incr cr_row_idx} {
      if { ! ${is_first_iteration} } {
        set start_cr_col_idx ${min_cr_col_idx}
      }

      for {set cr_col_idx ${start_cr_col_idx}} {${cr_col_idx} <= ${max_cr_col_idx}} {incr cr_col_idx} {
        set clock_region [get_clock_regions -of_objects ${slr} X${cr_col_idx}Y${cr_row_idx}]
        # puts "Processing clock region ${clock_region}"

        set cr_tiles [get_tiles -quiet -of_objects ${clock_region}]

        # Some clock regions could have nothing inside them. This often happens in Zynq devices as
        # some clock regions are taken up by hard processors. These processors are not visible in the
        # floorplan and are not returned as tiles when querying the contents of the clock region.
        if { [llength ${cr_tiles}] > 0 } {
          # Get the min/max col index for the tiles in the clock region.
          lassign [get_clock_region_tile_col_boundaries ${clock_region}] min_tile_col_idx max_tile_col_idx

          if { ! ${is_first_iteration} } {
            set start_tile_col_idx ${min_tile_col_idx}
          }

          # Iterate over the columns in the clock region in order.
          for {set tile_col_idx ${start_tile_col_idx}} {${tile_col_idx} <= ${max_tile_col_idx}} {incr tile_col_idx} {
            # puts "Processing tile column ${tile_col_idx}"

            set is_first_iteration 0

            # Tiles at the given column.
            # Note that we use "-quiet" as we know some columns contain no tiles (and hence no sites).
            # Vivado emts a warning for every such column it encounters and this gives
            # the impression something is wrong. However, we handle this case explicitly
            # in what follows, so we use "quiet" here to remove the warning.
            set tiles [get_tiles -quiet -of_objects ${clock_region} -filter "COLUMN == ${tile_col_idx} && TILE_TYPE == ${tile_type}"]

            if { [llength ${tiles}] > 0 } {
              puts "Found column of ${tile_type} at (${slr}, ${clock_region}, tile column ${tile_col_idx})"

              # We sort the sites to get them in increasing order of its Y coordinate. We can sort the
              # sites using `lsort -dictionary {list}` as all tiles have names like "<tile_name>_X(\d+)Y(\d+)"
              # and the X coordinate is identical between all entries (they are in the same column).
              # The entries will therefore be sorted by their Y-value.
              set tiles_sorted [lsort -dictionary ${tiles}]
              return [list ${slr_idx} ${cr_row_idx} ${cr_col_idx} ${tile_col_idx} ${tiles_sorted}]
            }; # non-empty tiles
          }; # clock region tile column idx
        }; # clock region empty?
      }; # clock region col idx
    }; # clock region row idx
  }; # SLR

  # We return the empty list if no tile is found.
  puts "No tile column exists with tile tyoe ${tile_type}"
  return {-1 -1 -1 -1 {}}
}

# Enumerates all sites in the first column that contains tiles/sites with the
# given TILE_TYPE/SITE_TYPE. This function searches for tile columns in the
# following order (SLR, row, col).
proc get_first_col_with_tileType_siteType { tile_type site_type } {
  set slr_idx 0
  set cr_row_idx 0
  set cr_col_idx 0
  set tile_col_idx 0

  while { 1 } {
    lassign [get_first_col_with_tileType ${tile_type} ${slr_idx} ${cr_row_idx} ${cr_col_idx} ${tile_col_idx}] slr_idx cr_row_idx cr_col_idx tile_col_idx tiles

    if { [llength ${tiles}] > 0 } {
      # Keep sites that correspond to the type we are looking for. We again use -quiet to avoid warnings
      # since we explicitly handle the case where there are no sites below.
      set sites [get_sites -quiet -of_objects ${tiles} -filter "SITE_TYPE == ${site_type}"]

      if { [llength ${sites}] > 0 } {
        puts "Found column of ${tile_type}/${site_type} at SLR ${slr_idx}, clock region row ${cr_row_idx}, clock region col ${cr_col_idx}, tile col ${tile_col_idx}"

        # We sort the sites to get them in increasing order of its Y coordinate. We can sort the
        # sites using `lsort -dictionary {list}` as all sites have names like "SLICE_X(\d+)Y(\d+)"
        # (or the name of any other site) and the X coordinate is identical between all entries
        # (they are in the same column). The entries will therefore be sorted by their Y-value.
        set sites_sorted [lsort -dictionary ${sites}]
        return ${sites_sorted}
      } else {
        # No sites were found in the tile column of interest. We retry the search for a new tile column
        # after the current column we stopped at.
        puts "Tile column ${tile_col_idx} contains tile type ${tile_type}, but no sites with site type ${site_type}. Continuing search."
        incr tile_col_idx
      }; # sites

    } else {
      # We return the empty list if no tile column is found.
      puts "No tile column exists with tile type ${tile_type}"
      return {}
    }; # tiles
  }
}

# Associates every SITE_TYPE with its corresponding TILE_TYPE. Returns a tuple
# of all possible (SITE_TYPE, TILE_TYPE) pairs.
proc get_siteType_tileType_pairs { site_types } {
  set siteType_tileType_pairs {}

  foreach site_type ${site_types} {
    set sites [get_sites -filter "SITE_TYPE == ${site_type}"]
    set tiles [get_tiles -of_objects ${sites}]
    set site_types [get_property SITE_TYPE ${sites}]
    set tile_types [get_property TILE_TYPE ${tiles}]

    foreach site_type ${site_types} tile_type ${tile_types} {
      lappend siteType_tileType_pairs [list ${site_type} ${tile_type}]
    }
  }

  set uniq [uniquify_list ${siteType_tileType_pairs}]
  return ${uniq}
}

# Converts a tcl list to a json list string. This essentially formats list
# boundaries with "[" and "]" as the "{" and "}" that TCL uses as list boundaries
# are illegal json.
proc tcl_list_to_json_list { l } {
  set lines {}
  foreach elem ${l} {
    lappend lines [tcl_to_json ${elem}]
  }
  return "\[[join ${lines} ","]\]"
}

# Converts a tcl data structure (string/list) to a json string.
# - If the input is a tcl list, then a json list is returned.
# - If the input is a tcl string, then a json string is returned.
proc tcl_to_json { list_or_str } {
  if { [llength ${list_or_str}] > 1 } {
    # must be a list as it has a length larger than 1.
    return [tcl_list_to_json_list ${list_or_str}]
  } else {
    set is_int [string is integer -strict ${list_or_str}]
    set is_float [string is double -strict ${list_or_str}]
    set is_number [expr ${is_int} || ${is_float}]
    if { ${is_number} } {
      # json does not require quotes around numbers.
      return "${list_or_str}"
    } else {
      # json requires quotes around strings.
      return "\"${list_or_str}\""
    }
  }
}

# Formats a json string by calling our json formatter.
proc format_json { json_str } {
  set script_path [file dirname [file normalize [info script]]]
  set format_json_script [file dirname ${script_path}]/format_json.py
  # set formatted [exec python3 -m json.tool << ${json_str}]
  set formatted [exec python3 ${format_json_script} --sort_keys << ${json_str}]
  return ${formatted}
}

# Taken from https://wiki.tcl-lang.org/page/Assertions
#
# Example:
#   assert {$argv==1} "usage : myscript.tcl filename"
proc assert {cond {msg "assertion failed"}} {
  if { ![uplevel 1 expr ${cond}] } {
    error ${msg}
  }
}

proc rand_n_bit_number_str { n } {
  set bits {}
  foreach idx [struct::list iota ${n}] {
    lappend bits "[expr round(rand())]"
  }
  return "[join ${bits} ""]"
}

proc rand_n_bit_verilog_number_str { n } {
  return "${n}'b[rand_n_bit_number_str ${n}]"
}

# Returns a one-hot binary equation of given length where the ${bit_idx}-th
# bit (from the right) is set to 1.
#
# Ex: If called with (64, 3), it will return
#   "0000000000000000000000000000000000000000000000000000000000001000"
proc one_hot_bin_str { length bit_idx } {
  # Note that indexing starts from the left in a list, but we want to create a
  # binary number and this involves counting from the right.
  set equation [lrepeat ${length} 0]
  set rev_idx [expr ${length} - 1 - ${bit_idx}]
  lset equation ${rev_idx} 1
  set equation_str_w_spaces [join ${equation}]
  # TCL cannot join lists without a delimiter (even putting "" as the delimiter
  # will cause the quotes themselves to appear in the final string). We therefore
  # just joing the list with the default " " delimiter then replace all whitespace
  # with an empty space afterwards.
  set equation_str_wo_spaces [string map {" " ""} ${equation_str_w_spaces}]
  return ${equation_str_wo_spaces}
}
