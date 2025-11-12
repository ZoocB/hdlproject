# handle_source_files.tcl - Source file handling
namespace eval handle_source_files {
    variable vhdl_files {}
    variable verilog_files {}
    variable systemverilog_files {}
    
    # Process source files from JSON
    proc process_source_files {files_list} {
        variable vhdl_files
        variable verilog_files
        variable systemverilog_files
        
        common::log_status "Handle HDL Source Files..."
        
        # Clear existing lists
        set vhdl_files {}
        set verilog_files {}
        set systemverilog_files {}
        
        # Process each file entry
        foreach file_entry $files_list {
            set file_type [dict get $file_entry type]
            set file_path [dict get $file_entry path]

            common::log_status "file_type: $file_type, file_path: $file_path"
            
            # Skip if file doesn't exist
            if {![file exists $file_path]} {
                common::log_warning "handle_source_files" "File not found: $file_path"
                continue
            }
            
            # Classify and collect files by type
            switch $file_type {
                "VHDL@2008" {
                    lappend vhdl_files [dict create path $file_path type $file_type library [dict get $file_entry library]]
                }
                "VHDL@1997" {
                    lappend vhdl_files [dict create path $file_path type $file_type library [dict get $file_entry library]]
                }
                "VHDL" {
                    lappend vhdl_files [dict create path $file_path type $file_type library [dict get $file_entry library]]
                }
                "Verilog" {
                    lappend verilog_files $file_path
                }
                "Systemverilog" {
                    lappend systemverilog_files $file_path
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
                if {$type eq "VHDL@2008"} {
                    set_property -name "file_type" -value "VHDL 2008" -objects $file_obj
                } else {
                    set_property -name "file_type" -value "VHDL" -objects $file_obj
                }
                
                # TODO: Set library property for VHDL file
                # This is where library management will be implemented
                # For now, adding a placeholder comment
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
        
        return [common::return_success [dict create \
            vhdl_files $vhdl_files \
            verilog_files $verilog_files \
            systemverilog_files $systemverilog_files]]
    }
    
    # Set top level file
    proc set_top_level {top_level_file_name} {
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
        
        return [common::return_success {}]
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
