# project_workflow.tcl - Main entry point script with clearer argument names
#!/usr/bin/env tclsh

variable script_dir [file dirname [file normalize [info script]]]

# Source required modules
source "$script_dir/common.tcl"
source "$script_dir/config.tcl"
source "$script_dir/handle_xcis.tcl"
source "$script_dir/handle_source_files.tcl"
source "$script_dir/handle_bds.tcl"
source "$script_dir/handle_constraints.tcl"
source "$script_dir/handle_synth_settings.tcl"
source "$script_dir/handle_impl_settings.tcl"
source "$script_dir/build.tcl"
source "$script_dir/export.tcl"

# Parse command line arguments with clearer names
proc parse_arguments {argv} {
    set args_dict [dict create]
    
    # Set defaults
    dict set args_dict mode ""
    dict set args_dict vivado_project_dir ""
    dict set args_dict project_root ""
    dict set args_dict cores 4
    dict set args_dict config_file "hdlproject_config.json"
    dict set args_dict compile_order_file "compile_order.json"
    
    # Parse arguments
    set i 0
    while {$i < [llength $argv]} {
        set arg [lindex $argv $i]
        switch -glob -- $arg {
            "-mode" - "--mode" {
                incr i
                dict set args_dict mode [lindex $argv $i]
            }
            "-vivado_project_dir" - "--vivado-project-dir" {
                incr i
                dict set args_dict vivado_project_dir [lindex $argv $i]
            }
            "-project_root" - "--project-root" {
                incr i
                dict set args_dict project_root [lindex $argv $i]
            }
            "-cores" - "--cores" {
                incr i
                dict set args_dict cores [lindex $argv $i]
            }
            "-config" - "--config" {
                incr i
                dict set args_dict config_file [lindex $argv $i]
            }
            "-compile_order" - "--compile-order" {
                incr i
                dict set args_dict compile_order_file [lindex $argv $i]
            }
            "-h" - "--help" {
                print_usage
                exit 0
            }
            default {
                puts "Error: Unknown argument '$arg'"
                print_usage
                exit 1
            }
        }
        incr i
    }
    
    # Validate required arguments
    if {[dict get $args_dict mode] eq ""} {
        puts "Error: Mode is required"
        print_usage
        exit 1
    }
    
    if {[dict get $args_dict vivado_project_dir] eq ""} {
        puts "Error: Vivado project directory is required"
        print_usage
        exit 1
    }
    
    if {[dict get $args_dict project_root] eq ""} {
        puts "Error: Project root directory is required"
        print_usage
        exit 1
    }
    
    # Validate mode
    set valid_modes [list "open" "build" "export"]
    if {[lsearch -exact $valid_modes [dict get $args_dict mode]] == -1} {
        puts "Error: Invalid mode '[dict get $args_dict mode]'. Must be one of: [join $valid_modes ", "]"
        print_usage
        exit 1
    }
    
    return $args_dict
}

proc print_usage {} {
    puts "Usage: vivado -mode tcl -source project_workflow.tcl -tclargs \[options\]"
    puts ""
    puts "Required options:"
    puts "  -mode, --mode <mode>                       Operation mode: open, build, or export"
    puts "  -vivado_project_dir, --vivado-project-dir  Directory where Vivado project (.xpr) will be created"
    puts "  -project_root, --project-root              Root directory of the project"
    puts ""
    puts "Optional options:"
    puts "  -cores, --cores <num>                      Number of CPU cores for build (default: 4)"
    puts "  -config, --config <file>                   Configuration file (default: hdlproject_config.json)"
    puts "  -compile_order, --compile-order            Compile order file (default: compile_order.json)"
    puts "  -h, --help                                 Show this help message"
    puts ""
    puts "Examples:"
    puts "  # Open project in GUI"
    puts "  vivado -mode tcl -source project_workflow.tcl -tclargs --mode open --vivado-project-dir ./build/project --project-root ."
    puts ""
    puts "  # Build project with 8 cores"
    puts "  vivado -mode tcl -source project_workflow.tcl -tclargs --mode build --vivado-project-dir ./build/project --project-root . --cores 8"
}

# Helper proc to handle step results - returns 1 if should exit due to error
proc handle_step_result {result step_name} {
    set status [dict get $result status]
    
    # Only exit on actual errors, not warnings
    if {$status eq "error"} {
        return 1
    }
    return 0
}

# Main script starts here
common::log_status "======= Vivado Project Management System ======="

# Parse arguments
set args_dict [parse_arguments $argv]

# Extract parsed arguments with clearer variable names
set script_mode_str [dict get $args_dict mode]
set vivado_project_dir [dict get $args_dict vivado_project_dir]
set project_root_dir [dict get $args_dict project_root]
set num_build_cores [dict get $args_dict cores]
set config_file_name [dict get $args_dict config_file]
set compile_order_file_name [dict get $args_dict compile_order_file]

switch $script_mode_str {
    "open"   { set script_mode $common::OPEN_MODE }
    "build"  { set script_mode $common::BUILD_MODE }
    "export" { set script_mode $common::EXPORT_MODE }
}

# ===============================================================================
# =========================== Project Configuration =============================
# ===============================================================================

# Get parent directory of vivado_project_dir (this is the operation directory)
set operation_dir [file dirname $vivado_project_dir]

# Construct full paths for config files
set compile_order_file_path "$operation_dir/$compile_order_file_name"

# Determine config file path - could be absolute or relative
if {[file pathtype $config_file_name] eq "absolute"} {
    set config_file_path $config_file_name
} else {
    # Check if it's a resolved config in operation dir
    if {[file exists "$operation_dir/$config_file_name"]} {
        set config_file_path "$operation_dir/$config_file_name"
    } else {
        set config_file_path "$project_root_dir/$config_file_name"
    }
}

common::log_status "Loading configuration from: $config_file_path"

# Load project configuration (could be original or pre-resolved)
set result [config::load_config $config_file_path]
if {[dict get $result status] eq "error"} {
    exit 1
}

# Extract configuration data
set project_info [config::get_project_info]
set device_info [config::get_device_info]

# Extract device information (with defaults)
if {[dict exists $device_info part_name]} {
    set part_name [dict get $device_info part_name]
} else {
    common::log_error "project_workflow" "Missing required device_info.part_name"
    exit 1
}

if {[dict exists $device_info board_name]} {
    set board_name [dict get $device_info board_name]
} else {
    set board_name ""
}

if {[dict exists $device_info board_part]} {
    set board_part [dict get $device_info board_part]
} else {
    set board_part ""
}

# Extract project information
set top_level_file_name [dict get $project_info top_level_file_name]
set project_name [dict get $project_info project_name]

# Extract Vivado version with defaults
if {[dict exists $device_info vivado_version_year]} {
    set vivado_version_year [dict get $device_info vivado_version_year]
} elseif {[dict exists $project_info vivado_version_year]} {
    set vivado_version_year [dict get $project_info vivado_version_year]
} else {
    # Default to current Vivado version
    set vivado_version_year [lindex [split [version -short] .] 0]
}

if {[dict exists $device_info vivado_version_sub]} {
    set vivado_version_sub [dict get $device_info vivado_version_sub]
} elseif {[dict exists $project_info vivado_version_sub]} {
    set vivado_version_sub [dict get $project_info vivado_version_sub]
} else {
    # Default to current Vivado version
    set vivado_version_sub [lindex [split [version -short] .] 1]
}

# ===============================================================================
# ============================= System Configuration ============================
# ===============================================================================

# Check for libcrypt library and append to LD_LIBRARY_PATH if needed (for Python bindings)
set dir "/usr/lib/x86_64-linux-gnu/"
if {[file isdirectory $dir]} {
    set env(OLD_LD_LIBRARY_PATH) $env(LD_LIBRARY_PATH)
    set env(LD_LIBRARY_PATH) "$env(LD_LIBRARY_PATH):$dir"
    common::log_status "Appended system $dir to LD_LIBRARY_PATH"
}

# Initialise project context (allows user scripts to call set_name)
project_context::initialise

# ===============================================================================
# ========================== Load compile order JSON ============================
# ===============================================================================
common::log_status "Loading compile order from: $compile_order_file_path"

# Check if compile order file exists
if {![file exists $compile_order_file_path]} {
    common::log_error "project_workflow" "Compile order file not found: $compile_order_file_path"
    exit 1
}

# Read and parse compile order JSON
if {[catch {
    set compile_order_handle [open $compile_order_file_path r]
    set compile_order_data [read $compile_order_handle]
    close $compile_order_handle
    set compile_order_dict [json::json2dict $compile_order_data]
} error_msg]} {
    common::log_error "project_workflow" "Failed to parse compile order file: $error_msg"
    exit 1
}

# Extract files list
if {![dict exists $compile_order_dict files]} {
    common::log_error "project_workflow" "Missing 'files' key in compile order JSON"
    exit 1
}
set files_list [dict get $compile_order_dict files]


# ===============================================================================
# =========================== Project creation and setup ========================
# ===============================================================================
common::log_status "Setting up Project..."

# Create standardised directories relative to vivado_project_dir
set bd_dir [file join [file dirname $vivado_project_dir] "bd"]
set xci_dir [file join [file dirname $vivado_project_dir] "xci"]

# Create directories
file mkdir $vivado_project_dir
file mkdir $bd_dir
file mkdir $xci_dir

# Create BD gitignore (for backward compatibility)
set gitignore_file "$bd_dir/.gitignore"
set gitignore_content "*\n"
set file_id [open $gitignore_file "w"]
puts $file_id $gitignore_content
close $file_id

# Create project
create_project -force $project_name $vivado_project_dir -part $part_name

# Set gitignore for project directory
set gitignore_file "$vivado_project_dir/.gitignore"
set gitignore_content "*\n"
set file_id [open $gitignore_file "w"]
puts $file_id $gitignore_content
close $file_id

# Set project properties
set obj [current_project]
if {$board_part ne ""} {
    set_property -name "board_part" -value "$board_part" -objects $obj
}
if {$board_name ne ""} {
    set_property -name "platform.board_id" -value "$board_name" -objects $obj
}

# Set standard project properties
set_property -name "default_lib" -value "work" -objects $obj
set_property -name "enable_vhdl_2008" -value "1" -objects $obj
set_property -name "ip_cache_permissions" -value "read write" -objects $obj
set_property -name "ip_output_repo" -value "$vivado_project_dir/${project_name}.cache/ip" -objects $obj
set_property -name "mem.enable_memory_map_generation" -value "1" -objects $obj
set_property -name "sim.central_dir" -value "$vivado_project_dir/${project_name}.ip_user_files" -objects $obj
set_property -name "sim.ip.auto_export_scripts" -value "1" -objects $obj
set_property -name "simulator_language" -value "Mixed" -objects $obj
set_property -name "target_language" -value "VHDL" -objects $obj
set_property -name "webtalk.activehdl_export_sim" -value "42" -objects $obj
set_property -name "webtalk.ies_export_sim" -value "42" -objects $obj
set_property -name "webtalk.modelsim_export_sim" -value "42" -objects $obj
set_property -name "webtalk.questa_export_sim" -value "42" -objects $obj
set_property -name "webtalk.riviera_export_sim" -value "42" -objects $obj
set_property -name "webtalk.vcs_export_sim" -value "42" -objects $obj
set_property -name "webtalk.xsim_export_sim" -value "42" -objects $obj
set_property -name "xpm_libraries" -value "XPM_CDC XPM_FIFO XPM_MEMORY" -objects $obj

# Create 'sources_1' fileset if not found
if {[string equal [get_filesets -quiet sources_1] ""]} {
    create_fileset -srcset sources_1
}

# Create simulation fileset
handle_source_files::create_sim_fileset

# ===============================================================================
# ======================= Process project components ============================
# ===============================================================================

# Track overall workflow status
set workflow_has_warnings 0
set workflow_has_errors 0

# Handle XCIs
set result [handle_xcis::process_xcis $files_list $vivado_project_dir $script_mode $xci_dir]
if {[dict get $result status] eq "error"} {
    set workflow_has_errors 1
} elseif {[dict get $result status] eq "warning"} {
    set workflow_has_warnings 1
}

# Handle source files
set result [handle_source_files::process_source_files $files_list]
if {[dict get $result status] eq "error"} {
    set workflow_has_errors 1
} elseif {[dict get $result status] eq "warning"} {
    set workflow_has_warnings 1
}

# Handle Constraints and TCL files
set result [handle_constraints::process_constraints $files_list]
if {[dict get $result status] eq "error"} {
    set workflow_has_errors 1
} elseif {[dict get $result status] eq "warning"} {
    set workflow_has_warnings 1
}

# Handle Block Designs
set result [handle_bds::process_bds $files_list $vivado_project_dir $bd_dir]
if {[dict get $result status] eq "error"} {
    set workflow_has_errors 1
} elseif {[dict get $result status] eq "warning"} {
    set workflow_has_warnings 1
}

# Set top level
set result [handle_source_files::set_top_level $top_level_file_name]
if {[dict get $result status] eq "error"} {
    set workflow_has_errors 1
} elseif {[dict get $result status] eq "warning"} {
    set workflow_has_warnings 1
}

# Configure synthesis settings
set result [handle_synth_settings::configure_synth_settings $part_name $vivado_version_year]
if {[dict get $result status] eq "error"} {
    set workflow_has_errors 1
} elseif {[dict get $result status] eq "warning"} {
    set workflow_has_warnings 1
}

# Apply custom synthesis options
set result [handle_synth_settings::apply_custom_synth_options]
if {[dict get $result status] eq "error"} {
    set workflow_has_errors 1
} elseif {[dict get $result status] eq "warning"} {
    set workflow_has_warnings 1
}

# Apply top-level generics
set result [handle_synth_settings::apply_top_level_generics]
if {[dict get $result status] eq "error"} {
    set workflow_has_errors 1
} elseif {[dict get $result status] eq "warning"} {
    set workflow_has_warnings 1
}

# Configure implementation settings
set result [handle_impl_settings::configure_impl_settings $part_name $vivado_version_year]
if {[dict get $result status] eq "error"} {
    set workflow_has_errors 1
} elseif {[dict get $result status] eq "warning"} {
    set workflow_has_warnings 1
}

# Apply custom implementation options
set result [handle_impl_settings::apply_custom_impl_options]
if {[dict get $result status] eq "error"} {
    set workflow_has_errors 1
} elseif {[dict get $result status] eq "warning"} {
    set workflow_has_warnings 1
}

# ===============================================================================
# ======================= Check for errors before proceeding ====================
# ===============================================================================

if {$workflow_has_errors} {
    common::log_error "project_workflow" "One or more steps failed during project setup"
    exit 1
}

# ===============================================================================
# ======================= Execute requested action ==============================
# ===============================================================================

# Execute based on mode
if {$script_mode == $common::BUILD_MODE} {
    # Build project (use project_root_dir and vivado_project_dir)
    set result [build::execute $project_root_dir $vivado_project_dir $num_build_cores $top_level_file_name]
    
    if {[dict get $result status] eq "error"} {
        exit 1
    }
    exit 0
    
} elseif {$script_mode == $common::OPEN_MODE} {
    # Print project context for Python to capture
    project_context::print_context
    
    # Open project in GUI
    common::log_status "Opening Vivado GUI"
    start_gui
    
} elseif {$script_mode == $common::EXPORT_MODE} {
    # Export project
    set result [export::execute $project_root_dir]
    if {[dict get $result status] eq "error"} {
        exit 1
    }
    exit 0
}