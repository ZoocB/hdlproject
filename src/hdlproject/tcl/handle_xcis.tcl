# handle_xcis.tcl - XCI file handling
namespace eval handle_xcis {
    # Process XCI files from JSON
    proc process_xcis {files_list project_dir script_mode local_xci_dir} {
        common::log_status "Handling XCIs..."
        
        # Suppress specific messages
        set_msg_config -id "Vivado 12-4371" -suppress
        set_msg_config -id "Vivado 12-1342" -suppress
        set_msg_config -id "Vivado 12-3645" -suppress
        
        # Get required configuration
        set device_info [config::get_device_info]
        set project_info [config::get_project_info]
        
        set part_name [dict get $device_info part_name]
        set vivado_version_year [dict get $project_info vivado_version_year]
        set vivado_version_sub [dict get $project_info vivado_version_sub]
        
        # Process each XCI file from the list
        foreach file_entry $files_list {
            if {[dict get $file_entry type] ne "XCI"} {
                continue
            }
            
            set xci_path [dict get $file_entry path]
            
            # Skip if file doesn't exist
            if {![file exists $xci_path]} {
                common::log_warning "handle_xcis" "XCI file not found: $xci_path"
                continue
            }
            
            # Check if XCI matches device and Vivado version
            if {![regexp "/${part_name}/vivado_${vivado_version_year}.${vivado_version_sub}/[file tail $xci_path]$" $xci_path]} {
                common::log_info "Skipping XCI file, $xci_path (does not match part and/or Vivado version)"
                continue
            }
            
            # Extract file name
            set file_name [file rootname [file tail $xci_path]]
            
            # Handle XCI based on script mode
            if {$script_mode == $common::BUILD_MODE} {
                # Create directory for XCI
                set xci_dir "$local_xci_dir/$file_name"
                file mkdir $xci_dir
                
                # Copy XCI file
                set local_xci_path "$xci_dir/$file_name.xci"
                file copy -force $xci_path $local_xci_path
            } else {
                # Use original XCI path
                set local_xci_path $xci_path
            }
            
            # Add XCI to project
            add_files -fileset sources_1 [file normalize "$local_xci_path"]
            
            # Note: COE file handling is now expected to be managed externally
            # The external module should provide COE files separately in the JSON
        }
        
        return [common::return_success {}]
    }
}