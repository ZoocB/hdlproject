# config.tcl

package require json

namespace eval config {
    variable config_dict {}
    variable device_info {}
    variable project_info {}
    
    # Load pre-resolved configuration file
    proc load_config {config_file} {
        variable config_dict
        variable project_info
        variable device_info
        
        if {![file exists $config_file]} {
            return [common::return_error "config" "Configuration file does not exist: $config_file"]
        }
        
        # Read config file
        if {[catch {
            set config_file_handle [open $config_file r]
            set config_data [read $config_file_handle]
            close $config_file_handle
            set config_dict [json::json2dict $config_data]
        } error_msg]} {
            return [common::return_error "config" "Failed to parse configuration file: $error_msg"]
        }
        
        # Extract basic config sections
        if {![dict exists $config_dict project_information]} {
            return [common::return_error "config" "Missing project_information in configuration"]
        }
        
        set project_info [dict get $config_dict project_information]
        
        if {[dict exists $project_info device_info]} {
            set device_info [dict get $project_info device_info]
        } else {
            set device_info {}
        }
        
        return [common::return_success $config_dict]
    }
    
    # Get synthesis options as a dictionary
    proc get_synth_options {} {
        variable config_dict
        
        if {[dict exists $config_dict synth_options]} {
            set options [dict get $config_dict synth_options]
            # Handle both dictionary and list formats
            if {[llength $options] == 1 && [string is list $options]} {
                set first_item [lindex $options 0]
                if {[string match "*\{*" $first_item]} {
                    # It's a list containing a dict, extract the dict
                    return $first_item
                }
            }
            # New dictionary format or already extracted
            return $options
        }
        return {}
    }
    
    # Get implementation options as a dictionary
    proc get_impl_options {} {
        variable config_dict
        
        if {[dict exists $config_dict impl_options]} {
            set options [dict get $config_dict impl_options]
            # Handle both dictionary and list formats
            if {[llength $options] == 1 && [string is list $options]} {
                set first_item [lindex $options 0]
                if {[string match "*\{*" $first_item]} {
                    # It's a list containing a dict, extract the dict
                    return $first_item
                }
            }
            # New dictionary format or already extracted
            return $options
        }
        return {}
    }

    proc get_build_configuration {} {
        variable config_dict
        if {[dict exists $config_dict build_configuration]} {
            return [dict get $config_dict build_configuration]
        }
        return {}
    }
    
    # Apply synthesis options to project
    proc apply_synth_options {project_name} {
        set synth_options [get_synth_options]
        
        if {[llength $synth_options] > 0} {
            common::log_info  "Applying synthesis options..."
            dict for {property value} $synth_options {
                if {[catch {
                    set_property $property $value [get_runs synth_1]
                    common::log_info  "  Set $property = $value"
                } error_msg]} {
                    common::log_warning "config" "  Failed to set $property: $error_msg"
                }
            }
        }
    }
    
    # Apply implementation options to project
    proc apply_impl_options {project_name} {
        set impl_options [get_impl_options]
        
        if {[llength $impl_options] > 0} {
            common::log_info  "Applying implementation options..."
            dict for {property value} $impl_options {
                if {[catch {
                    set_property $property $value [get_runs impl_1]
                    common::log_info  "  Set $property = $value"
                } error_msg]} {
                    common::log_warning "config" "  Failed to set $property: $error_msg"
                }
            }
        }
    }

    # Various getters
    proc get_config {} {
        variable config_dict
        return $config_dict
    }
    
    proc get_device_info {} {
        variable device_info
        return $device_info
    }
    
    proc get_project_info {} {
        variable project_info
        return $project_info
    }
}