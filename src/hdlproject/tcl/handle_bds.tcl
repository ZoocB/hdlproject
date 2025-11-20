# handle_bds.tcl - Block design handling
namespace eval handle_bds {
    # Process block designs from JSON
    proc process_bds {files_list project_dir local_bd_dir} {
        common::log_status "Handle BD files..."
        
        # Get configuration
        set config_dict [config::get_config]
        
        # Get BD files from the files list (primary source)
        set bd_files {}
        foreach file_entry $files_list {
            if {[dict get $file_entry type] eq "X_BD"} {
                lappend bd_files [dict get $file_entry path]
            }
        }
        
        # Check if we have any BD files to process
        if {[llength $bd_files] == 0} {
            common::log_info "No block design files found in files_list"
            return [common::return_success {}]
        }
        
        # Get block designs from configuration (optional, for commands only)
        set block_designs {}
        if {[dict exists $config_dict block_designs]} {
            set block_designs [dict get $config_dict block_designs]
        }
        
        # Create a dictionary mapping BD filenames to their commands (if any)
        set bd_commands_dict {}
        foreach bd_entry $block_designs {
            if {![dict exists $bd_entry file]} {
                common::log_warning "handle_bds" "Missing 'file' key in block design entry"
                continue
            }
            
            set bd_filename [dict get $bd_entry file]
            
            # Check if this BD exists in files_list
            if {[catch {_check_bd_file_matches $bd_filename $bd_files} bd_filepath]} {
                return [common::return_error "handle_bds" "BD '$bd_filename' defined in configuration but not found in files_list"]
            }
            
            # Store commands if they exist
            if {[dict exists $bd_entry commands]} {
                dict set bd_commands_dict $bd_filename [dict get $bd_entry commands]
            }
        }
        
        # Process all BD files from files_list
        if {[catch {
            foreach bd_filepath $bd_files {
                # Skip if path contains local_bd_dir
                if {[string match "*local_bd_dir*" $bd_filepath]} {
                    common::log_debug "Skipping BD in local_bd_dir: $bd_filepath"
                    continue
                }
                
                set bd_filename [file tail $bd_filepath]
                
                # Check if this BD has commands to execute
                if {[dict exists $bd_commands_dict $bd_filename]} {
                    # Copy BD to local directory and process commands
                    set local_bd_path [_copy_bd_to_local_project $bd_filename $bd_filepath $local_bd_dir]
                    add_files -fileset sources_1 $local_bd_path
                    
                    open_bd_design $local_bd_path
                    if {[current_bd_design] eq ""} {
                        return [common::return_error "handle_bds" "Failed to open BD design $local_bd_path"]
                    } else {
                        common::log_info "Opening BD Design $local_bd_path"
                    }
                    
                    # Execute BD commands
                    set commands [dict get $bd_commands_dict $bd_filename]
                    set bd_cmd_results [_execute_bd_commands $commands]
                    set bd_error 0
                    
                    foreach result $bd_cmd_results {
                        set status [dict get $result status]
                        set command [dict get $result command]
                        set output [dict get $result result]
                        
                        if {$status == "error"} {
                            common::log_error "handle_bds" "cmd: $command, msg: $output"
                            set bd_error 1
                        } elseif {$status == "warning"} {
                            common::log_warning "handle_bds" "cmd: $command, msg: $output"
                        } else {
                            common::log_info "cmd: $command, msg: SUCCESS"
                        }
                    }
                    
                    # Save design if no errors
                    if {$bd_error == 0} {
                        eval save_bd_design
                    }
                } else {
                    # No commands for this BD, just add it to the project
                    common::log_debug "Adding BD without commands: $bd_filepath"
                    add_files -fileset sources_1 $bd_filepath
                }
            }
        } error_msg]} {
            if {$error_msg ne ""} {
                return [common::return_error "handle_bds" "Processing block designs: $error_msg"]
            }
        }
        
        return [common::return_success {}]
    }
    
    # Check if BD filename matches one in the list
    proc _check_bd_file_matches {bd_filename bd_list} {
        # Search for matching filenames in the bd_list
        set matches {}
        
        foreach bd_path $bd_list {
            # Skip this path if any directory contains `local_bd_dir`
            set skip 0
            set dir $bd_path
            common::log_debug "bd_dir: $dir"
            
            while {$dir ne "" && $dir ne "/"} {
                if {[string match "*local_bd_dir*" [file tail $dir]]} {
                    common::log_debug "skipping bd"
                    set skip 1
                    break
                }
                set dir [file dirname $dir]
            }
            
            # If skip is set, move to the next path
            if {$skip} {
                continue
            }
            
            if {[file tail $bd_path] eq $bd_filename} {
                lappend matches $bd_path
            }
        }
        
        # Check the number of matches
        set match_count [llength $matches]
        if {$match_count == 0} {
            error "ERROR: No matching block design found for filename: $bd_filename"
        } elseif {$match_count > 1} {
            error "ERROR: Multiple matches found for filename: $bd_filename\nMatches: [join $matches \n]"
        }
        
        return [lindex $matches 0]
    }
    
    # Copy BD to local project directory
    proc _copy_bd_to_local_project {bd_filename bd_filepath local_bd_dir} {
        set file_name [file rootname [file tail $bd_filename]]
        set bd_dir "$local_bd_dir/$file_name"
        file mkdir $bd_dir
        set local_bd_path "$bd_dir/$file_name.bd"
        file copy -force $bd_filepath $local_bd_path
        
        return $local_bd_path
    }
    
    # Execute BD commands
    proc _execute_bd_commands {commands} {
        # Initialise variables
        set current_command ""
        set in_multiline 0
        set results []
        
        foreach command $commands {
            # Remove any trailing whitespace
            set command [string trim $command]
            
            # Check if command ends with backslash (indicates multi-line command)
            if {[string match {*\\} $command]} {
                # Remove the trailing backslash and append to current command
                set command [string range $command 0 end-1]
                append current_command $command " "
                set in_multiline 1
                continue
            }
            
            # If we're in a multiline command, append this part
            if {$in_multiline} {
                append current_command $command
                set in_multiline 0
                set command $current_command
                set current_command ""
            }
            
            # Execute the command (either single line or completed multiline)
            if {[catch {eval $command} result]} {
                lappend results [dict create \
                    status "error" \
                    command $command \
                    result $result \
                ]
            } else {
                lappend results [dict create \
                    status "success" \
                    command $command \
                    result $result \
                ]
            }
        }
        
        # Check if there's an uncompleted multiline command
        if {$in_multiline} {
            set warning_msg "Uncompleted multiline command found: $current_command"
            lappend results [dict create \
                status "warning" \
                command $current_command \
                result $warning_msg \
            ]
        }
        
        return $results
    }
}