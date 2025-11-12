# export.tcl - Export project

namespace eval export {
    # Export project as zip/tar.gz archive
    proc execute {repo_prj_dir} {
        # Get project file name
        set project_info [config::get_project_info]
        set device_info [config::get_device_info]
        
        set project_name [dict get $project_info project_name]
        set upper_project_name [string toupper $project_name]
        
        if {[dict exists $device_info board_name]} {
            set upper_board_name [string toupper [dict get $device_info board_name]]
        } else {
            set upper_board_name "GENERIC"
        }
        
        # Build export name from project info and timestamp
        set timestamp [clock format [clock seconds] -format "%Y%m%d_%H%M%S"]
        set export_name "${upper_project_name}_${upper_board_name}_${timestamp}"
        
        # If there are version generics, append them
        if {[dict exists $project_info top_level_generics]} {
            set generics [dict get $project_info top_level_generics]
            
            # Look for version information in generics
            set version_string ""
            foreach {major minor patch} {"VERSION_MAJOR" "VERSION_MINOR" "VERSION_PATCH"} {
                if {[dict exists $generics $major] && 
                    [dict exists $generics $minor] && 
                    [dict exists $generics $patch]} {
                    set v_major [dict get $generics $major value]
                    set v_minor [dict get $generics $minor value]
                    set v_patch [dict get $generics $patch value]
                    set version_string "v${v_major}.${v_minor}.${v_patch}"
                    break
                }
            }
            
            if {$version_string ne ""} {
                set export_name "${upper_project_name}_${upper_board_name}_${version_string}_${timestamp}"
            }
        }
        
        # Create zip archive
        set archive_zip "${repo_prj_dir}/build_artefacts/${export_name}.zip"
        archive_project -force -exclude_run_results $archive_zip
        
        # Convert to tar.gz
        set archive_file "${repo_prj_dir}/build_artefacts/${export_name}"
        
        # Create a temporary directory
        set temp_dir [exec mktemp -d]
        # Unzip the file to the temporary directory
        exec unzip $archive_zip -d $temp_dir
        # Create a tar.gz file from the contents of the temporary directory
        exec tar -czf ${archive_file}.tar.gz -C $temp_dir .
        # Remove the original zip file if needed
        file delete ${archive_file}.zip
        # Clean up temp directory
        file delete -force $temp_dir
        
        common::log_status "Project exported to ${archive_file}.tar.gz"
        
        # Also create a JSON manifest with export information
        set manifest [dict create \
            export_date [clock format [clock seconds] -format "%Y-%m-%d %H:%M:%S"] \
            project_name $project_name \
            export_file "${export_name}.tar.gz" \
        ]
        
        # Add configuration info
        if {[dict exists $device_info part_name]} {
            dict set manifest device_part [dict get $device_info part_name]
        }
        
        # Add generic values if present
        if {[dict exists $project_info top_level_generics]} {
            set generic_values [dict create]
            dict for {name def} [dict get $project_info top_level_generics] {
                if {![dict exists $def runtime] || ![dict get $def runtime]} {
                    dict set generic_values $name [dict get $def value]
                }
            }
            dict set manifest generics $generic_values
        }
        
        # Write manifest
        set manifest_file "${repo_prj_dir}/build_artefacts/${export_name}_manifest.json"
        if {[catch {
            package require json::write
            set fp [open $manifest_file w]
            puts $fp [json::write object {*}$manifest]
            close $fp
        } error_msg]} {
            common::log_warning "export" "Could not write manifest file: $error_msg"
        }
        
        return [common::return_success {}]
    }
}