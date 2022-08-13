# author: Sahand Kashani <sahand.kashani@epfl.ch>

# To call this script, use the following command:
#
#   vivado -mode batch -source get_parts.tcl -notrace -tclargs [-keep_webpack_only] <arch_name_pattern_regex> <json_out>
#
# Example:
#
#   vivado -mode batch -source get_parts.tcl -notrace -tclargs ".*" output.json
#
# The output of this script is a single file defined by the <json_out> argument.

package require cmdline
package require struct::list

source [file join [file dirname [info script]] helpers.tcl]

proc is_webpack_part { part } {
  set license [get_property LICENSE ${part}]
  return [string match "Webpack" ${license}]
}

proc main { arch_name_pattern_regex json_out keep_webpack_only } {
  # Bucketize all parts.
  set part_arch_dict [dict create]
  set part_device_dict [dict create]
  set arch_devices_dict [dict create]
  set device_parts_dict [dict create]

  foreach part [get_parts] {
    # Note that ARCHITECTURE_FULL_NAME is a list, not a string.
    set arch [get_property ARCHITECTURE_FULL_NAME ${part}]
    set device [get_property DEVICE ${part}]
    # Every part has ONE architecture/device -> `set`.
    dict set part_arch_dict ${part} ${arch}
    dict set part_device_dict ${part} ${device}
    # Every arch has multiple devices -> `lappend`.
    dict lappend arch_devices_dict ${arch} ${device}
    # Every device has multiple parts -> `lappend`
    dict lappend device_parts_dict ${device} ${part}
  }

  # Remove duplicates from the various buckets (many parts are from the same device).
  dict for { arch devices } ${arch_devices_dict} {
    dict set arch_devices_dict ${arch} [uniquify_list ${devices}]
  }
  dict for { device parts } ${device_parts_dict} {
    dict set device_parts_dict ${device} [uniquify_list ${parts}]
  }

  # Emit json string. We sort the entries before emitting them.
  set arch_lines {}
  foreach arch [lsort [dict keys ${arch_devices_dict}]] {
    if { [regexp -nocase ${arch_name_pattern_regex} ${arch}] } {

      set device_lines {}
      set devices [dict get ${arch_devices_dict} ${arch}]
      foreach device [lsort -dictionary ${devices}] {
        set parts [dict get ${device_parts_dict} ${device}]

        if { ${keep_webpack_only} } {
          # We only emit entries for which we need the "Webpack" license, i.e., parts
          # that we can generate a bitstream for without having a full license.
          set parts_filtered [struct::list filter ${parts} is_webpack_part]
        } else {
          set parts_filtered ${parts}
        }

        set parts_filtered_sorted [lsort -dictionary ${parts_filtered}]
        lappend device_lines "\"${device}\": [tcl_list_to_json_list ${parts_filtered_sorted}]"
      }; # devices

      lappend arch_lines "\"${arch}\": \{[join ${device_lines} ","]\}"
    }; # if arch pattern ok
  }; # archs
  set json_str "\{[join ${arch_lines} ","]\}"

  set file_out [open ${json_out} w]
  puts ${file_out} [format_json ${json_str}]
  close ${file_out}
}

set cli_options {
  { "keep_webpack_only" "Only keep parts that require a Webpack license to implement" }
}
set cli_usage ": get_parts \[options\] json_out \noptions:"

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
  puts "expected mandatory args: <arch_name_pattern_regex> <json_out>"
} else {
  set arch_name_pattern_regex [lindex $::argv 0]
  set json_out [lindex $::argv 1]
  main ${arch_name_pattern_regex} ${json_out} $options(keep_webpack_only)
}
