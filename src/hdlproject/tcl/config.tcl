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
                # Legacy list format - check if it's a list with one dict
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
                # Legacy list format - check if it's a list with one dict
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

    # Convert typed generic to HDL string - FIXED to prevent spaces and format correctly
    proc generic_to_hdl_string {name generic_def} {
        set type [dict get $generic_def type]
        set value [dict get $generic_def value]
        
        # Trim all values to remove any whitespace
        set type [string trim $type]
        set value [string trim $value]
        set name [string trim $name]
        
        # Build the result string carefully using format to ensure no newlines
        switch $type {
            "std_logic" {
                # Format: -generic NAME=1'b0
                return [format {-generic %s=1'b%s} $name $value]
            }
            "std_logic_vector" {
                set width [string trim [dict get $generic_def width]]
                set format "hex"
                if {[dict exists $generic_def format]} {
                    set format [string trim [dict get $generic_def format]]
                }
                
                switch $format {
                    "hex" {
                        set formatted_value [format_hex_value $value $width]
                        # Format: -generic NAME=32'hDAC00001
                        return [format {-generic %s=%s'h%s} $name $width $formatted_value]
                    }
                    "binary" {
                        set formatted_value [format_binary_value $value $width]
                        # Format: -generic NAME=2'b10
                        return [format {-generic %s=%s'b%s} $name $width $formatted_value]
                    }
                    "decimal" {
                        # Format: -generic NAME=32'd123
                        return [format {-generic %s=%s'd%s} $name $width $value]
                    }
                    default {
                        # Default to hex format
                        set formatted_value [format_hex_value $value $width]
                        return [format {-generic %s=%s'h%s} $name $width $formatted_value]
                    }
                }
            }
            "unsigned" -
            "signed" {
                set width [string trim [dict get $generic_def width]]
                # Format: -generic NAME=8'd7
                return [format {-generic %s=%s'd%s} $name $width $value]
            }
            "integer" {
                # Format: -generic NAME=8
                return [format {-generic %s=%s} $name $value]
            }
            "real" {
                # Format: -generic NAME=125.5
                return [format {-generic %s=%s} $name $value]
            }
            "boolean" {
                # Convert boolean to 1 or 0
                if {[string is true -strict $value] || $value == "true" || $value == 1} {
                    set bit_value "1"
                } else {
                    set bit_value "0"
                }
                # Format: -generic NAME=1'b1
                return [format {-generic %s=1'b%s} $name $bit_value]
            }
            "string" {
                # Format: -generic NAME="value"
                return [format {-generic %s="%s"} $name $value]
            }
            default {
                common::log_warning "config" "Unknown generic type '$type' for '$name', using raw value"
                return [format {-generic %s=%s} $name $value]
            }
        }
    }
    
    # Format hex value
    proc format_hex_value {value width} {
        # Remove 0x prefix if present
        if {[string match "0x*" $value] || [string match "0X*" $value]} {
            set value [string range $value 2 end]
        }
        # Remove any whitespace
        set value [string trim $value]
        # Convert to uppercase
        set value [string toupper $value]
        # Calculate required hex digits
        set hex_digits [expr {($width + 3) / 4}]
        # Pad with zeros if needed
        while {[string length $value] < $hex_digits} {
            set value "0${value}"
        }
        return $value
    }
    
    # Format binary value
    proc format_binary_value {value width} {
        # Remove 0b prefix if present
        if {[string match "0b*" $value] || [string match "0B*" $value]} {
            set value [string range $value 2 end]
        }
        # Remove any whitespace
        set value [string trim $value]
        # Pad with zeros if needed
        while {[string length $value] < $width} {
            set value "0${value}"
        }
        return $value
    }
    
    # Get all generics as HDL parameters
    proc get_generics_as_hdl {} {
        variable project_info
        
        if {![dict exists $project_info top_level_generics]} {
            return ""
        }
        
        set generics [dict get $project_info top_level_generics]
        set hdl_params {}
        
        dict for {name generic_def} $generics {
            # Skip runtime generics that weren't resolved
            if {[dict exists $generic_def runtime] && [dict get $generic_def runtime]} {
                set value [dict get $generic_def value]
                if {[string match "*\$\{*\}*" $value]} {
                    common::log_warning "config" "Skipping unresolved runtime generic: $name = $value"
                    continue
                }
            }
            
            set param [generic_to_hdl_string $name $generic_def]
            lappend hdl_params $param
        }
        
        # Join with single spaces
        return [join $hdl_params " "]
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