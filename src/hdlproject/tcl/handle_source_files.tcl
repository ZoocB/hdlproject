# handle_source_files.tcl - Source file handling with improved logging
namespace eval handle_source_files {
    # Module names for logging
    variable MODULE_NAME "handle_source_files"
    variable MODULE_NAME_TOP "handle_source_files::set_top_level"
    
    variable vhdl_files {}
    variable verilog_files {}
    variable systemverilog_files {}
    
    # Process source files from JSON
    proc process_source_files {files_list} {
        variable MODULE_NAME
        variable vhdl_files
        variable verilog_files
        variable systemverilog_files
        
        # Initialise logging for this module
        common::log_init $MODULE_NAME
        
        common::log_status "Handle HDL Source Files..."
        
        # Clear existing lists
        set vhdl_files {}
        set verilog_files {}
        set systemverilog_files {}
        
        set files_added 0
        set files_skipped 0
        
        # Process each file entry
        foreach file_entry $files_list {
            set file_type [dict get $file_entry type]
            set file_path [file normalize [dict get $file_entry path]]
          
            # Only get ver_tag if it exists
            if {[dict exists $file_entry ver_tag]} {
                set file_ver_tag [dict get $file_entry ver_tag]
            } else {
                set file_ver_tag ""
            }

            # Skip if file doesn't exist
            if {![file exists $file_path]} {
                common::log_warning $MODULE_NAME "File not found: $file_path"
                incr files_skipped
                continue
            }
            
            # Classify and collect files by type
            switch $file_type {
                "VHDL" {
                  switch $file_ver_tag {
                    "VHDL2008" {
                      lappend vhdl_files [dict create path $file_path type VHDL2008 library [dict get $file_entry library]]
                      common::log_status "Adding file_type: $file_type, file_path: $file_path"
                      incr files_added
                    }
                    default {
                      lappend vhdl_files [dict create path $file_path type VHDL library [dict get $file_entry library]]
                      common::log_status "Adding file_type: $file_type, file_path: $file_path"
                      incr files_added
                    }
                  }
                }
                "VERILOG" {
                    lappend verilog_files $file_path
                    common::log_status "Adding file_type: $file_type, file_path: $file_path"
                    incr files_added
                }
                "SYSTEMVERILOG" {
                    lappend systemverilog_files $file_path
                    common::log_status "Adding file_type: $file_type, file_path: $file_path"
                    incr files_added
                }
            }
        }
        
        # Add files to project
        common::log_status "Adding all source files to project..."
        set num_vhdl_files [llength $vhdl_files]
        set num_verilog_files [llength $verilog_files]
        set num_systemverilog_files [llength $systemverilog_files]

        common::log_status "num_vhdl_files: $num_vhdl_files"
        common::log_status "num_verilog_files: $num_verilog_files"
        common::log_status "num_systemverilog_files: $num_systemverilog_files"

        # Add VHDL files with library management
        if { $num_vhdl_files > 0 } {
            foreach vhdl_entry $vhdl_files {
                set path [dict get $vhdl_entry path]
                set type [dict get $vhdl_entry type]
                set library [dict get $vhdl_entry library]
                
                # Add file to project
                add_files -fileset sources_1 $path
                
                # Get file object
                set file_obj [get_files -of_objects [get_filesets sources_1] [list "*$path"]]
                # Set VHDL version
                if {$type eq "VHDL2008"} {
                    set_property -name "file_type" -value "VHDL 2008" -objects $file_obj
                } else {
                    set_property -name "file_type" -value "VHDL" -objects $file_obj
                }
                
                set_property -name "library" -value $library -objects $file_obj
                common::log_status "Set library '$library' for VHDL file: [file tail $path]"
            }
        }
        
        # Add Verilog files
        if {[llength $verilog_files] > 0} {
            add_files -fileset sources_1 {*}$verilog_files
        }
        
        # Add SystemVerilog files
        if {[llength $systemverilog_files] > 0} {
            add_files -fileset sources_1 {*}$systemverilog_files
            
            # Set file type to SystemVerilog
            foreach sv_file $systemverilog_files {
                set file_obj [get_files -of_objects [get_filesets sources_1] [list "*$sv_file"]]
                set_property -name "file_type" -value "SystemVerilog" -objects $file_obj
            }
        }
        
        common::log_status "Source file handling complete. Added $files_added file(s), skipped $files_skipped file(s)."
        
        # Return result using automatic tracking
        return [common::report_step_result "handle_source_files::process_source_files" $MODULE_NAME \
            [dict create \
                vhdl_files $vhdl_files \
                verilog_files $verilog_files \
                systemverilog_files $systemverilog_files \
                files_added $files_added \
                files_skipped $files_skipped]]
    }
    
    # Set top level file
    proc set_top_level {top_level_file_name} {
        variable MODULE_NAME_TOP
        
        # Initialise logging for this module
        common::log_init $MODULE_NAME_TOP
        
        # Set top level for sources_1 fileset
        set obj [get_filesets sources_1]
        set_property -name "top" -value "$top_level_file_name" -objects $obj
        # set_property -name "top_auto_set" -value "0" -objects $obj
        
        # Set top level for simulation if it exists
        if {![string equal [get_filesets -quiet sim_1] ""]} {
            set obj [get_filesets sim_1]
            set_property -name "top" -value "$top_level_file_name" -objects $obj
            # set_property -name "top_auto_set" -value "0" -objects $obj
            set_property -name "top_lib" -value "xil_defaultlib" -objects $obj
        }
        
        # Return result using automatic tracking
        return [common::report_step_result "handle_source_files::set_top_level" $MODULE_NAME_TOP]
    }
    
    # Create simulation fileset if needed
    proc create_sim_fileset {} {
        # Create 'sim_1' fileset if not found
        if {[string equal [get_filesets -quiet sim_1] ""]} {
            create_fileset -simset sim_1
        }
        
        return [common::return_success {}]
    }
}