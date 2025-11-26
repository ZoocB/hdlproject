# common.tcl - Shared utilities and common functions with improved logging system

namespace eval common {
    # Mode constants
    variable OPEN_MODE 0
    variable BUILD_MODE 1
    variable EXPORT_MODE 2
    
    # Step result prefixes for Python parsing
    variable STEP_SUCCESS_PREFIX "\[HDLPROJECT_STEP_SUCCESS\]"
    variable STEP_WARNING_PREFIX "\[HDLPROJECT_STEP_WARNING\]"
    variable STEP_ERROR_PREFIX "\[HDLPROJECT_STEP_ERROR\]"
    
    # =========================================================================
    # Log Tracking System
    # =========================================================================
    # Tracks warnings and errors per module for automatic result determination
    
    variable log_counts
    array set log_counts {}
    
    # Initialise or reset log counts for a module
    proc log_init {module_name} {
        variable log_counts
        set log_counts(${module_name},warnings) 0
        set log_counts(${module_name},errors) 0
        set log_counts(${module_name},messages) {}
    }
    
    # Get current warning count for a module
    proc log_get_warning_count {module_name} {
        variable log_counts
        if {[info exists log_counts(${module_name},warnings)]} {
            return $log_counts(${module_name},warnings)
        }
        return 0
    }
    
    # Get current error count for a module
    proc log_get_error_count {module_name} {
        variable log_counts
        if {[info exists log_counts(${module_name},errors)]} {
            return $log_counts(${module_name},errors)
        }
        return 0
    }
    
    # Get all messages for a module
    proc log_get_messages {module_name} {
        variable log_counts
        if {[info exists log_counts(${module_name},messages)]} {
            return $log_counts(${module_name},messages)
        }
        return {}
    }
    
    # Increment warning count and store message
    proc log_add_warning {module_name message} {
        variable log_counts
        if {![info exists log_counts(${module_name},warnings)]} {
            log_init $module_name
        }
        incr log_counts(${module_name},warnings)
        lappend log_counts(${module_name},messages) [list warning $message]
    }
    
    # Increment error count and store message
    proc log_add_error {module_name message} {
        variable log_counts
        if {![info exists log_counts(${module_name},errors)]} {
            log_init $module_name
        }
        incr log_counts(${module_name},errors)
        lappend log_counts(${module_name},messages) [list error $message]
    }
    
    # =========================================================================
    # Logging Functions
    # =========================================================================
    
    proc log_status {message} {
        puts "$message"
    }
    
    proc log_info {message} {
        puts "INFO: $message"
    }
    
    # Log warning and track it
    proc log_warning {module_name message} {
        puts "WARNING: $module_name - $message"
        log_add_warning $module_name $message
    }
    
    # Log error and track it
    proc log_error {module_name message} {
        puts "ERROR: $module_name - $message"
        log_add_error $module_name $message
    }
    
    proc log_debug {message} {
        puts "debug: $message"
    }
    
    # =========================================================================
    # Step Result Functions - Output parseable markers for Python
    # =========================================================================
    
    # Print step success with optional counts
    proc step_success {step_name {message ""}} {
        variable STEP_SUCCESS_PREFIX
        if {$message eq ""} {
            puts "$STEP_SUCCESS_PREFIX $step_name"
        } else {
            puts "$STEP_SUCCESS_PREFIX $step_name - $message"
        }
    }
    
    # Print step warning with counts
    proc step_warning {step_name warning_count {error_count 0} {message ""}} {
        variable STEP_WARNING_PREFIX
        set count_str "W:$warning_count"
        if {$error_count > 0} {
            append count_str " E:$error_count"
        }
        if {$message eq ""} {
            puts "$STEP_WARNING_PREFIX $step_name \[$count_str\]"
        } else {
            puts "$STEP_WARNING_PREFIX $step_name \[$count_str\] - $message"
        }
    }
    
    # Print step error with counts
    proc step_error {step_name error_count {warning_count 0} {message ""}} {
        variable STEP_ERROR_PREFIX
        set count_str "E:$error_count"
        if {$warning_count > 0} {
            append count_str " W:$warning_count"
        }
        if {$message eq ""} {
            puts "$STEP_ERROR_PREFIX $step_name \[$count_str\]"
        } else {
            puts "$STEP_ERROR_PREFIX $step_name \[$count_str\] - $message"
        }
    }
    
    # =========================================================================
    # Result Handling
    # =========================================================================

    proc return_success {data} {
        return [dict create status "success" data $data warnings 0 errors 0]
    }
    
    proc return_warning {module_name message} {
        log_warning $module_name $message
        set warn_count [log_get_warning_count $module_name]
        set err_count [log_get_error_count $module_name]
        return [dict create status "warning" message $message warnings $warn_count errors $err_count]
    }
    
    proc return_error {module_name message} {
        log_error $module_name $message
        set warn_count [log_get_warning_count $module_name]
        set err_count [log_get_error_count $module_name]
        return [dict create status "error" message $message warnings $warn_count errors $err_count]
    }
    
    # Automatically determine result based on logged warnings/errors for a module
    # This is the preferred way to return from a step
    proc return_step_result {module_name {data {}}} {
        set warn_count [log_get_warning_count $module_name]
        set err_count [log_get_error_count $module_name]
        
        if {$err_count > 0} {
            return [dict create status "error" data $data warnings $warn_count errors $err_count]
        } elseif {$warn_count > 0} {
            return [dict create status "warning" data $data warnings $warn_count errors $err_count]
        } else {
            return [dict create status "success" data $data warnings 0 errors 0]
        }
    }
    
    # =========================================================================
    # Step Result Reporting - Combines result with parseable output
    # =========================================================================
    
    # Report step result - prints the appropriate marker and returns the result
    # Use this at the end of each handler process
    proc report_step_result {step_name module_name {data {}}} {
        set result [return_step_result $module_name $data]
        set status [dict get $result status]
        set warn_count [dict get $result warnings]
        set err_count [dict get $result errors]
        
        switch $status {
            "success" {
                step_success $step_name
            }
            "warning" {
                step_warning $step_name $warn_count $err_count
            }
            "error" {
                step_error $step_name $err_count $warn_count
            }
        }
        
        return $result
    }
    
    # =========================================================================
    # Utility Functions
    # =========================================================================
    
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