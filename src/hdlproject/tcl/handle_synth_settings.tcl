# handle_synth_settings.tcl - Synthesis settings with improved logging

namespace eval handle_synth_settings {
    # Module names for logging
    variable MODULE_NAME_CONFIG "handle_synth_settings::configure"
    variable MODULE_NAME_OPTIONS "handle_synth_settings::apply_options"
    variable MODULE_NAME_GENERICS "handle_synth_settings::apply_generics"
    
    # Configure synthesis settings
    proc configure_synth_settings {part_name vivado_version_year} {
        variable MODULE_NAME_CONFIG
        
        # Initialise logging for this module
        common::log_init $MODULE_NAME_CONFIG
        
        common::log_status "Setting Synthesis Settings..."
        
        # Create synth_1 run if it doesn't exist
        if {[string equal [get_runs -quiet synth_1] ""]} {
            create_run -name synth_1 -part $part_name -flow {Vivado Synthesis $vivado_version_year} -strategy "Vivado Synthesis Defaults" -report_strategy {No Reports} -constrset constrs_1
        } else {
            set_property strategy "Vivado Synthesis Defaults" [get_runs synth_1]
            set_property flow "Vivado Synthesis $vivado_version_year" [get_runs synth_1]
        }
        
        # Setup report strategy
        set obj [get_runs synth_1]
        set_property set_report_strategy_name 1 $obj
        set_property report_strategy {Vivado Synthesis Default Reports} $obj
        set_property set_report_strategy_name 0 $obj
        
        # Create utilization report if not found
        if {[string equal [get_report_configs -of_objects [get_runs synth_1] synth_1_synth_report_utilization_0] ""]} {
            create_report_config -report_name synth_1_synth_report_utilization_0 -report_type report_utilization:1.0 -steps synth_design -runs synth_1
        }
        
        # Set basic properties
        set_property -name "part" -value "$part_name" -objects $obj
        set_property -name "strategy" -value "Vivado Synthesis Defaults" -objects $obj
        
        # Default options
        set_property -name "STEPS.SYNTH_DESIGN.ARGS.ASSERT" -value "true" -objects [get_runs synth_1]
        
        # Return result using automatic tracking
        return [common::report_step_result "handle_synth_settings::configure_synth_settings" $MODULE_NAME_CONFIG]
    }
    
    # Apply custom synthesis options (NOT for generics!)
    proc apply_custom_synth_options {} {
        variable MODULE_NAME_OPTIONS
        
        # Initialise logging for this module
        common::log_init $MODULE_NAME_OPTIONS
        
        common::log_status "Applying custom synthesis options..."
        
        set options_applied 0
        
        # Get synthesis options using the config namespace function
        set synth_options [config::get_synth_options]
        
        if {[llength $synth_options] > 0} {
            common::log_info "\tSetting custom synth options"
            dict for {key value} $synth_options {
                # Apply each synthesis option
                if {[catch {
                    set_property -name $key -value $value -objects [get_runs synth_1]
                    common::log_info "\t\toption: $key = $value"
                    incr options_applied
                } err]} {
                    common::log_warning $MODULE_NAME_OPTIONS "Failed to set option $key: $err"
                }
            }
        } else {
            common::log_info "\tNo custom synthesis options defined"
        }
        
        # Return result using automatic tracking
        return [common::report_step_result "handle_synth_settings::apply_custom_synth_options" $MODULE_NAME_OPTIONS \
            [dict create options_applied $options_applied]]
    }
    
    # Apply top-level generics to synthesis
    proc apply_top_level_generics {} {
        variable MODULE_NAME_GENERICS
        
        # Initialise logging for this module
        common::log_init $MODULE_NAME_GENERICS
        
        common::log_status "Applying top-level generics..."
        
        # Get HDL formatted generics from config
        set hdl_generics [config::get_generics_as_hdl]

        puts "hdl_generics: $hdl_generics"
        
        if {$hdl_generics eq ""} {
            common::log_info "\tNo top-level generics defined"
            return [common::report_step_result "handle_synth_settings::apply_top_level_generics" $MODULE_NAME_GENERICS]
        }
        
        # MORE OPTIONS is the correct property for generics
        set more_options "STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS"
        
        # Get current MORE OPTIONS value (might be empty)
        set current_options ""
        if {[catch {
            set current_options [get_property $more_options [get_runs synth_1]]
        }]} {
            # Property might not exist yet, that's OK
            set current_options ""
        }
        
        # Append our generics to any existing options
        if {$current_options ne ""} {
            # There are existing options, append with a space
            set new_options "$current_options $hdl_generics"
        } else {
            # No existing options, just use our generics
            set new_options $hdl_generics
        }
        
        # Set the property
        if {[catch {
            set_property -name $more_options -value $new_options -objects [get_runs synth_1]
        } err]} {
            common::log_error $MODULE_NAME_GENERICS "Failed to set MORE OPTIONS: $err"
            return [common::report_step_result "handle_synth_settings::apply_top_level_generics" $MODULE_NAME_GENERICS]
        }
        
        # Log what we applied
        common::log_info "\tApplied generics to MORE OPTIONS:"
        common::log_info "\t\t$hdl_generics"
        
        # Log each generic individually for clarity
        foreach generic [split $hdl_generics " -generic "] {
            if {$generic ne ""} {
                common::log_info "\t\t-generic $generic"
            }
        }
        
        # Set the current synth run
        current_run -synthesis [get_runs synth_1]
        
        # Return result using automatic tracking
        return [common::report_step_result "handle_synth_settings::apply_top_level_generics" $MODULE_NAME_GENERICS]
    }
}