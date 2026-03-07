# handle_constraints.tcl - Constraint and TCL file handling with improved logging
namespace eval handle_constraints {
    # Module name for logging
    variable MODULE_NAME "handle_constraints"
    
    # Process constraint files from configuration only
    proc process_constraints {files_list} {
        variable MODULE_NAME
        
        # Initialise logging for this module
        common::log_init $MODULE_NAME
        
        common::log_status "Handling Constraints and TCL files..."

        set constraints_added 0
        set tcl_executed 0
        
        # Create filesets if needed
        if {[string equal [get_filesets -quiet constrs_1] ""]} {
            create_fileset -constrset constrs_1
        }
        
        if {[string equal [get_filesets -quiet utils_1] ""]} {
            create_fileset -utils utils_1
        }
        
        # Get configuration data
        set config_dict [config::get_config]
        
        # Check if constraints section exists
        if {![dict exists $config_dict constraints]} {
            common::log_info "No constraints section found in configuration"
            return [common::report_step_result "handle_constraints::process_constraints" $MODULE_NAME]
        }
        
        set config_constraints [dict get $config_dict constraints]
        
        # Build a lookup table of files from compile order (filename -> full path)
        set file_lookup [dict create]
        foreach file_entry $files_list {
            set file_type [dict get $file_entry type]
            set file_path [dict get $file_entry path]

            if {[dict exists $file_entry file_ext]} {
                set file_extension [dict get $file_entry file_ext]
            } else {
                # Skip constraint files without a file extension type (kind of hacky...)
                continue
            }
            
            if {$file_type eq "EXTERNAL"} {
                if {$file_extension eq "XDC" || $file_extension eq "TCL"} {
                    set filename [file tail $file_path]
                    dict set file_lookup $filename $file_path
                }
            }
        }
        
        # Process each constraint entry from configuration
        foreach constraint $config_constraints {
            if {$constraint eq ""} {
                continue
            }
            
            # Get file name from constraint entry
            if {![dict exists $constraint file]} {
                common::log_warning $MODULE_NAME "Constraint entry missing 'file' key"
                continue
            }
            
            set file_name [dict get $constraint file]
            
            # Find the full path from compile order
            if {![dict exists $file_lookup $file_name]} {
                common::log_warning $MODULE_NAME "File '$file_name' specified in config but not found in compile order"
                continue
            }
            
            set full_path [file normalize [dict get $file_lookup $file_name]]

            # Check if file exists
            if {![file exists $full_path]} {
                common::log_warning $MODULE_NAME "File not found: $full_path"
                continue
            }
            
            # Determine file type based on extension
            set file_ext [file extension $full_path]
            set is_tcl [expr {$file_ext eq ".tcl"}]
            set is_xdc [expr {$file_ext eq ".xdc"}]
            
            # Process properties
            set target_fileset "constrs_1"  ; # Default fileset
            set immediate_execution 0
            set properties_to_apply {}
            
            if {[dict exists $constraint properties]} {
                set properties [dict get $constraint properties]
                
                foreach prop_dict $properties {
                    dict for {prop_name prop_value} $prop_dict {
                        if {$prop_name eq "FILESET"} {
                            # Special handling for fileset property
                            set target_fileset $prop_value
                        } elseif {$prop_name eq "execution" && $prop_value eq "immediate"} {
                            # Mark for immediate execution
                            set immediate_execution 1
                        } else {
                            # Store other properties to apply after adding file
                            lappend properties_to_apply [list $prop_name $prop_value]
                        }
                    }
                }
            }
            
            # Handle immediate execution for TCL files
            if {$is_tcl && $immediate_execution} {
                common::log_info "Executing TCL script immediately: $file_name"
                if {[catch {source $full_path} error_msg]} {
                    common::log_error $MODULE_NAME "Error executing TCL script '$file_name': $error_msg"
                    continue
                }
                common::log_info "Successfully executed TCL script: $file_name"
                incr tcl_executed
                # Don't add to project if executed immediately
                continue
            }
            
            # Add file to the appropriate fileset
            if {$is_xdc} {
                # XDC files always go to constraints fileset
                common::log_info "Adding XDC file '$file_name' to $target_fileset"
                add_files -fileset $target_fileset $full_path
                
                # Set as target constraints file if needed
                set_property target_constrs_file $full_path [current_fileset -constrset]
                incr constraints_added
            } elseif {$is_tcl} {
                # TCL files can go to different filesets
                common::log_info "Adding TCL file '$file_name' to $target_fileset"
                
                if {$target_fileset eq "constrs_1"} {
                    add_files -fileset constrs_1 $full_path
                    incr constraints_added
                } elseif {$target_fileset eq "utils_1"} {
                    add_files -fileset utils_1 $full_path
                    incr constraints_added
                } else {
                    common::log_warning $MODULE_NAME "Unknown fileset '$target_fileset' for TCL file '$file_name', using utils_1"
                    add_files -fileset utils_1 $full_path
                    incr constraints_added
                }
            } else {
                common::log_warning $MODULE_NAME "Unknown file type for: $file_name"
                continue
            }
            
            # Apply remaining properties to the file
            if {[llength $properties_to_apply] > 0} {
                # Get the file object
                set file_obj ""
                if {$target_fileset eq "constrs_1"} {
                    set file_obj [get_files -of_objects [get_filesets constrs_1] [list "*$full_path"]]
                } elseif {$target_fileset eq "utils_1"} {
                    set file_obj [get_files -of_objects [get_filesets utils_1] [list "*$full_path"]]
                }
                
                if {$file_obj ne ""} {
                    foreach prop_pair $properties_to_apply {
                        set prop_name [lindex $prop_pair 0]
                        set prop_value [lindex $prop_pair 1]
                        
                        if {[catch {
                            set_property $prop_name $prop_value $file_obj
                            common::log_info "  Set property $prop_name = $prop_value"
                        } error_msg]} {
                            common::log_warning $MODULE_NAME "Failed to set property $prop_name on file '$file_name': $error_msg"
                        }
                    }
                }
            }
        }

        common::log_status "Constraint handling complete. Added $constraints_added constraint(s), executed $tcl_executed TCL script(s)."
        
        # Return result using automatic tracking
        return [common::report_step_result "handle_constraints::process_constraints" $MODULE_NAME \
            [dict create constraints_added $constraints_added tcl_executed $tcl_executed]]
    }
}