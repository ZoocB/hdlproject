# handle_constraints.tcl - Constraint and TCL file handling
namespace eval handle_constraints {
    # Process constraint files from configuration only
    proc process_constraints {files_list} {
        common::log_status "Handling Constraints and TCL files..."

        set constraint_issues false
        
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
            return [common::return_success {}]
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
                common::log_warning "handle_constraints" "Constraint entry missing 'file' key"
                set constraint_issues true
                continue
            }
            
            set file_name [dict get $constraint file]
            
            # Find the full path from compile order
            if {![dict exists $file_lookup $file_name]} {
                common::log_warning "handle_constraints" "File '$file_name' specified in config but not found in compile order"
                set constraint_issues true
                continue
            }
            
            set full_path [file normalize [dict get $file_lookup $file_name]]

            # Check if file exists
            if {![file exists $full_path]} {
                common::log_warning "handle_constraints" "File not found: $full_path"
                set constraint_issues true
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
                    common::log_error "handle_constraints" "Error executing TCL script '$file_name': $error_msg"
                    set constraint_issues true
                    continue
                }
                common::log_info "Successfully executed TCL script: $file_name"
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
            } elseif {$is_tcl} {
                # TCL files can go to different filesets
                common::log_info "Adding TCL file '$file_name' to $target_fileset"
                
                if {$target_fileset eq "constrs_1"} {
                    add_files -fileset constrs_1 $full_path
                } elseif {$target_fileset eq "utils_1"} {
                    add_files -fileset utils_1 $full_path
                } else {
                    common::log_warning "handle_constraints" "Unknown fileset '$target_fileset' for TCL file '$file_name', using utils_1"
                    set constraint_issues true
                    add_files -fileset utils_1 $full_path
                }
            } else {
                common::log_warning "handle_constraints" "Unknown file type for: $file_name"
                set constraint_issues true
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
                            common::log_warning "handle_constraints" "Failed to set property $prop_name on file '$file_name': $error_msg"
                            set constraint_issues true
                        }
                    }
                }
            }
        }

        if {$constraint_issues} {
          return [return_error "handle_constraints.tcl" "Issues found"]
        } else {
          return [common::return_success {}]
        }
    }
}