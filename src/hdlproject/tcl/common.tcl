# common.tcl - Shared utilities and common functions

namespace eval common {
    # Mode constants
    variable OPEN_MODE 0
    variable BUILD_MODE 1
    variable EXPORT_MODE 2
    
    # Logging functions
    proc log_status {message} {
        puts "$message"
    }
    
    proc log_info {message} {
        puts "INFO: $message"
    }
    
    proc log_warning {script_name message} {
        puts "WARNING: $script_name - $message"
    }
    
    proc log_error {script_name message} {
        puts "ERROR: $script_name - $message"
    }
    
    proc log_debug {message} {
        puts "debug: $message"
    }
    
    # Result handling
    proc return_success {data} {
        return [dict create status "success" data $data]
    }
    
    proc return_error {script_name message} {
        log_error $script_name $message
        return [dict create status "error" message $message]
    }
    
    # Time formatting
    proc format_time_interval {intervalSeconds} {
        # *Assume* that the interval is positive
        set s [expr {$intervalSeconds % 60}]
        set i [expr {$intervalSeconds / 60}]
        set m [expr {$i % 60}]
        set i [expr {$i / 60}]
        set h [expr {$i % 24}]
        set d [expr {$i / 24}]
        return [format "%+d:%02d:%02d:%02d" $d $h $m $s]
    }

    # Environment variable substitution
    proc substitute_env_vars {text} {
        set result $text
        
        # Pattern for ${VAR_NAME}
        set pattern {\$\{([A-Z_][A-Z0-9_]*)\}}
        
        while {[regexp $pattern $result match var_name]} {
            if {[info exists ::env($var_name)]} {
                set var_value $::env($var_name)
            } else {
                log_debug "Environment variable '$var_name' not found"
                set var_value ""
            }
            set result [string map [list "\${$var_name}" $var_value] $result]
        }
        
        return $result
    }
}