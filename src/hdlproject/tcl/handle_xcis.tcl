# handle_xcis.tcl - XCI file handling with improved logging
namespace eval handle_xcis {
    # Module name for logging
    variable MODULE_NAME "handle_xcis"

    proc extract_coefficient_path {content xci_dir} {
        # JSON format: "Coefficient_File" : [ { "value" : "path/to/file.coe" } ]
        if {[string match {*"ip_inst"*} $content]} {
            foreach param {Coefficient_File Coe_File coefficient_file coe_file} {
                # Match any text between "value" : " and the closing "
                set re "\"$param\"\[^\"\]*\"value\"\[^\"\]*\"(\[^\"\]+)\""
                if {[regexp $re $content -> path]} {
                    return [file normalize [file join $xci_dir [string trim $path]]]
                }
            }
        } else {
            # XML format: referenceId="PARAM_VALUE.Coefficient_File">path/to/file.coe</
            foreach param {Coefficient_File Coe_File CoefFile coefficient_file} {
                # Match any text between > and <
                set re "referenceId=\"PARAM_VALUE.$param\">(\[^<\]+)<"
                if {[regexp $re $content -> path]} {
                    return [file normalize [file join $xci_dir [string trim $path]]]
                }
            }
        }
        return ""
    }

    proc update_xci_coefficient_path {xci_path coef_filename} {
        set f [open $xci_path r]
        set data [read $f]
        close $f

        set new_ref "../coefficients/$coef_filename"

        # JSON format: find "value" : "some/path.coe" and replace the path
        if {[string match {*"ip_inst"*} $data]} {
            foreach param {Coefficient_File Coe_File coefficient_file coe_file} {
                # Find the old path first
                set re_find "\"$param\"\[^\"\]*\"value\"\[^\"\]*\"(\[^\"\]+)\""
                if {[regexp $re_find $data -> old_path]} {
                    # Replace old path with new path using string map
                    set data [string map [list $old_path $new_ref] $data]
                }
            }
        } else {
            # XML format: find >some/path.coe< and replace the path
            foreach param {Coefficient_File Coe_File CoefFile coefficient_file} {
                # Find the old path first
                set re_find "referenceId=\"PARAM_VALUE.$param\">(\[^<\]+)<"
                if {[regexp $re_find $data -> old_path]} {
                    # Replace old path with new path using string map
                    set data [string map [list $old_path $new_ref] $data]
                }
            }
        }

        set f [open $xci_path w]
        puts -nonewline $f $data
        close $f
    }

    proc process_xcis {files_list project_dir script_mode local_xci_dir} {
        variable MODULE_NAME
        
        # Initialise logging for this module
        common::log_init $MODULE_NAME
        
        common::log_status "Handling XCIs (Build Mode = [expr {$script_mode == $common::BUILD_MODE ? "YES" : "NO"}])..."

        catch {set_msg_config -id {Vivado 12-4371} -suppress}
        catch {set_msg_config -id {Vivado 12-1342} -suppress}
        catch {set_msg_config -id {Vivado 12-3645} -suppress}

        array set xci_to_coef {}
        set xci_count 0
        set coef_count 0

        # ================================================================
        # PASS 1: Discover all coefficient dependencies
        # ================================================================
        foreach file_entry $files_list {
            if {[dict get $file_entry type] ne "X_XCI"} continue

            set xci_path [dict get $file_entry path]
            if {![file exists $xci_path]} {
                common::log_warning $MODULE_NAME "XCI not found: $xci_path"
                continue
            }

            set xci_abs [file normalize $xci_path]
            set xci_dir [file dirname $xci_path]

            set f [open $xci_path r]
            set content [read $f]
            close $f

            set coef_path [extract_coefficient_path $content $xci_dir]
            if {$coef_path ne "" && [file exists $coef_path]} {
                set xci_to_coef($xci_abs) $coef_path
            }
        }

        # ================================================================
        # BUILD_MODE: Copy + restructure with shared coefficients
        # ================================================================
        if {$script_mode == $common::BUILD_MODE} {
            set coef_dir "$local_xci_dir/coefficients"
            file mkdir $coef_dir
            array set copied_coef {}

            # First: Copy and add all coefficient files
            foreach xci_abs [array names xci_to_coef] {
                set orig_coef $xci_to_coef($xci_abs)
                set coef_name [file tail $orig_coef]
                set target_coef "$coef_dir/$coef_name"

                if {![info exists copied_coef($coef_name)]} {
                    file copy -force $orig_coef $target_coef
                    add_files -fileset sources_1 $target_coef
                    set copied_coef($coef_name) 1
                    incr coef_count
                    common::log_info "Copied shared coef → $target_coef"
                }
            }

            # Second: Copy XCIs, update references, and add them
            foreach file_entry $files_list {
                if {[dict get $file_entry type] ne "X_XCI"} continue
                set xci_path [dict get $file_entry path]
                if {![file exists $xci_path]} {
                    common::log_warning $MODULE_NAME "XCI file not found during copy: $xci_path"
                    continue
                }

                set xci_abs  [file normalize $xci_path]
                set xci_name [file rootname [file tail $xci_path]]

                set local_subdir "$local_xci_dir/$xci_name"
                file mkdir $local_subdir
                set local_xci "$local_subdir/$xci_name.xci"

                file copy -force $xci_path $local_xci

                if {[info exists xci_to_coef($xci_abs)]} {
                    set coef_name [file tail $xci_to_coef($xci_abs)]
                    update_xci_coefficient_path $local_xci $coef_name
                }

                add_files -fileset sources_1 $local_xci
                incr xci_count
                common::log_info "Added restructured XCI → $local_xci"
            }

        } else {
            # ================================================================
            # NON-BUILD_MODE: Just add original files — preserve original paths
            # ================================================================
            foreach file_entry $files_list {
                if {[dict get $file_entry type] ne "X_XCI"} continue

                set xci_path [dict get $file_entry path]
                if {![file exists $xci_path]} {
                    common::log_warning $MODULE_NAME "XCI file not found: $xci_path"
                    continue
                }

                set xci_abs [file normalize $xci_path]
                add_files -fileset sources_1 $xci_path
                incr xci_count
                common::log_info "Added original XCI: $xci_path"

                if {[info exists xci_to_coef($xci_abs)]} {
                    set coef_path $xci_to_coef($xci_abs)
                    add_files -fileset sources_1 $coef_path
                    incr coef_count
                    common::log_info "Added original coef: $coef_path"
                }
            }
        }

        common::log_status "XCI handling complete. Processed $xci_count XCI(s), $coef_count coefficient file(s)."
        
        # Return result using automatic tracking
        return [common::report_step_result "handle_xcis::process_xcis" $MODULE_NAME \
            [dict create xci_count $xci_count coef_count $coef_count]]
    }
}