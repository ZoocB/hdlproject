# handle_impl_settings.tcl - Implementation settings

namespace eval handle_impl_settings {
    # Configure implementation settings
    proc configure_impl_settings {part_name vivado_version_year} {
        common::log_status "Setting Implementation Settings..."
        
        # Create or update impl_1 run
        if {[string equal [get_runs -quiet impl_1] ""]} {
            create_run -name impl_1 -part $part_name -flow {Vivado Implementation $vivado_version_year} -strategy "Vivado Implementation Defaults" -report_strategy {No Reports} -constrset constrs_1 -parent_run synth_1
        } else {
            set_property strategy "Vivado Implementation Defaults" [get_runs impl_1]
            set_property flow "Vivado Implementation $vivado_version_year" [get_runs impl_1]
        }
        
        # Configure report strategy
        set obj [get_runs impl_1]
        set_property set_report_strategy_name 1 $obj
        set_property report_strategy {Vivado Implementation Default Reports} $obj
        set_property set_report_strategy_name 0 $obj
        
        # Setup standard reports
        _setup_impl_reports
        
        # Set basic properties
        set obj [get_runs impl_1]
        set_property -name "part" -value "$part_name" -objects $obj
        set_property -name "strategy" -value "Vivado Implementation Defaults" -objects $obj
        set_property -name "steps.write_bitstream.args.readback_file" -value "0" -objects $obj
        set_property -name "steps.write_bitstream.args.verbose" -value "0" -objects $obj
        
        # Create dashboard gadgets
        _create_dashboard_gadgets
        
        # Set the current impl run
        current_run -implementation [get_runs impl_1]
        
        return [common::return_success {}]
    }
    
    # Apply custom implementation options
    proc apply_custom_impl_options {} {
        common::log_status "Applying custom implementation options..."
        
        # Get implementation options using the config namespace function
        set impl_options [config::get_impl_options]
        
        if {[llength $impl_options] > 0} {
            common::log_info "\tSetting custom impl options"
            dict for {key value} $impl_options {
                # Apply each implementation option
                if {[catch {
                    set_property -name $key -value $value -objects [get_runs impl_1]
                    common::log_info "\t\toption: $key = $value"
                } err]} {
                    common::log_warning "handle_impl_settings" "Failed to set option $key: $err"
                }
            }
        } else {
            common::log_info "\tNo custom implementation options defined"
        }
        
        return [common::return_success {}]
    }
    
    # Create implementation reports
    proc _setup_impl_reports {} {
        # Create 'impl_1_init_report_timing_summary_0' report (if not found)
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_init_report_timing_summary_0] ""]} {
            create_report_config -report_name impl_1_init_report_timing_summary_0 -report_type report_timing_summary:1.0 -steps init_design -runs impl_1
        }
        
        set obj [get_report_configs -of_objects [get_runs impl_1] impl_1_init_report_timing_summary_0]
        if {$obj != ""} {
            set_property -name "is_enabled" -value "0" -objects $obj
            set_property -name "options.max_paths" -value "10" -objects $obj
        }
        
        # Create 'impl_1_opt_report_drc_0' report (if not found)
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_opt_report_drc_0] ""]} {
            create_report_config -report_name impl_1_opt_report_drc_0 -report_type report_drc:1.0 -steps opt_design -runs impl_1
        }
        
        # Create 'impl_1_opt_report_timing_summary_0' report (if not found)
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_opt_report_timing_summary_0] ""]} {
            create_report_config -report_name impl_1_opt_report_timing_summary_0 -report_type report_timing_summary:1.0 -steps opt_design -runs impl_1
        }
        
        set obj [get_report_configs -of_objects [get_runs impl_1] impl_1_opt_report_timing_summary_0]
        if {$obj != ""} {
            set_property -name "is_enabled" -value "0" -objects $obj
            set_property -name "options.max_paths" -value "10" -objects $obj
        }
        
        # Create 'impl_1_power_opt_report_timing_summary_0' report (if not found)
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_power_opt_report_timing_summary_0] ""]} {
            create_report_config -report_name impl_1_power_opt_report_timing_summary_0 -report_type report_timing_summary:1.0 -steps power_opt_design -runs impl_1
        }
        
        set obj [get_report_configs -of_objects [get_runs impl_1] impl_1_power_opt_report_timing_summary_0]
        if {$obj != ""} {
            set_property -name "is_enabled" -value "0" -objects $obj
            set_property -name "options.max_paths" -value "10" -objects $obj
        }
        
        # Create additional standard reports (place, route, etc.)
        _create_place_reports
        _create_route_reports
        _create_post_place_reports
        _create_post_route_reports
    }
    
    # Create place design reports
    proc _create_place_reports {} {
        # Create 'impl_1_place_report_io_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_place_report_io_0] ""]} {
            create_report_config -report_name impl_1_place_report_io_0 -report_type report_io:1.0 -steps place_design -runs impl_1
        }
        
        # Create 'impl_1_place_report_utilization_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_place_report_utilization_0] ""]} {
            create_report_config -report_name impl_1_place_report_utilization_0 -report_type report_utilization:1.0 -steps place_design -runs impl_1
        }
        
        # Create 'impl_1_place_report_control_sets_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_place_report_control_sets_0] ""]} {
            create_report_config -report_name impl_1_place_report_control_sets_0 -report_type report_control_sets:1.0 -steps place_design -runs impl_1
        }
        
        set obj [get_report_configs -of_objects [get_runs impl_1] impl_1_place_report_control_sets_0]
        if {$obj != ""} {
            set_property -name "options.verbose" -value "1" -objects $obj
        }
        
        # Create 'impl_1_place_report_incremental_reuse_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_place_report_incremental_reuse_0] ""]} {
            create_report_config -report_name impl_1_place_report_incremental_reuse_0 -report_type report_incremental_reuse:1.0 -steps place_design -runs impl_1
        }
        
        set obj [get_report_configs -of_objects [get_runs impl_1] impl_1_place_report_incremental_reuse_0]
        if {$obj != ""} {
            set_property -name "is_enabled" -value "0" -objects $obj
        }
        
        # Create additional place reports
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_place_report_incremental_reuse_1] ""]} {
            create_report_config -report_name impl_1_place_report_incremental_reuse_1 -report_type report_incremental_reuse:1.0 -steps place_design -runs impl_1
        }
        
        set obj [get_report_configs -of_objects [get_runs impl_1] impl_1_place_report_incremental_reuse_1]
        if {$obj != ""} {
            set_property -name "is_enabled" -value "0" -objects $obj
        }
        
        # Create place timing report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_place_report_timing_summary_0] ""]} {
            create_report_config -report_name impl_1_place_report_timing_summary_0 -report_type report_timing_summary:1.0 -steps place_design -runs impl_1
        }
        
        set obj [get_report_configs -of_objects [get_runs impl_1] impl_1_place_report_timing_summary_0]
        if {$obj != ""} {
            set_property -name "is_enabled" -value "0" -objects $obj
            set_property -name "options.max_paths" -value "10" -objects $obj
        }
    }
    
    # Create route design reports
    proc _create_route_reports {} {
        # Create 'impl_1_route_report_drc_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_route_report_drc_0] ""]} {
            create_report_config -report_name impl_1_route_report_drc_0 -report_type report_drc:1.0 -steps route_design -runs impl_1
        }
        
        # Create 'impl_1_route_report_methodology_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_route_report_methodology_0] ""]} {
            create_report_config -report_name impl_1_route_report_methodology_0 -report_type report_methodology:1.0 -steps route_design -runs impl_1
        }
        
        # Create 'impl_1_route_report_power_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_route_report_power_0] ""]} {
            create_report_config -report_name impl_1_route_report_power_0 -report_type report_power:1.0 -steps route_design -runs impl_1
        }
        
        # Create 'impl_1_route_report_route_status_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_route_report_route_status_0] ""]} {
            create_report_config -report_name impl_1_route_report_route_status_0 -report_type report_route_status:1.0 -steps route_design -runs impl_1
        }
        
        # Create 'impl_1_route_report_timing_summary_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_route_report_timing_summary_0] ""]} {
            create_report_config -report_name impl_1_route_report_timing_summary_0 -report_type report_timing_summary:1.0 -steps route_design -runs impl_1
        }
        
        set obj [get_report_configs -of_objects [get_runs impl_1] impl_1_route_report_timing_summary_0]
        if {$obj != ""} {
            set_property -name "options.max_paths" -value "10" -objects $obj
        }
        
        # Create 'impl_1_route_report_incremental_reuse_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_route_report_incremental_reuse_0] ""]} {
            create_report_config -report_name impl_1_route_report_incremental_reuse_0 -report_type report_incremental_reuse:1.0 -steps route_design -runs impl_1
        }
        
        # Create 'impl_1_route_report_clock_utilization_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_route_report_clock_utilization_0] ""]} {
            create_report_config -report_name impl_1_route_report_clock_utilization_0 -report_type report_clock_utilization:1.0 -steps route_design -runs impl_1
        }
        
        # Create 'impl_1_route_report_bus_skew_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_route_report_bus_skew_0] ""]} {
            create_report_config -report_name impl_1_route_report_bus_skew_0 -report_type report_bus_skew:1.1 -steps route_design -runs impl_1
        }
        
        set obj [get_report_configs -of_objects [get_runs impl_1] impl_1_route_report_bus_skew_0]
        if {$obj != ""} {
            set_property -name "options.warn_on_violation" -value "1" -objects $obj
        }
    }
    
    # Create post place reports
    proc _create_post_place_reports {} {
        # Create 'impl_1_post_place_power_opt_report_timing_summary_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_post_place_power_opt_report_timing_summary_0] ""]} {
            create_report_config -report_name impl_1_post_place_power_opt_report_timing_summary_0 -report_type report_timing_summary:1.0 -steps post_place_power_opt_design -runs impl_1
        }
        
        set obj [get_report_configs -of_objects [get_runs impl_1] impl_1_post_place_power_opt_report_timing_summary_0]
        if {$obj != ""} {
            set_property -name "is_enabled" -value "0" -objects $obj
            set_property -name "options.max_paths" -value "10" -objects $obj
        }
        
        # Create 'impl_1_phys_opt_report_timing_summary_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_phys_opt_report_timing_summary_0] ""]} {
            create_report_config -report_name impl_1_phys_opt_report_timing_summary_0 -report_type report_timing_summary:1.0 -steps phys_opt_design -runs impl_1
        }
        
        set obj [get_report_configs -of_objects [get_runs impl_1] impl_1_phys_opt_report_timing_summary_0]
        if {$obj != ""} {
            set_property -name "is_enabled" -value "0" -objects $obj
            set_property -name "options.max_paths" -value "10" -objects $obj
        }
    }
    
    # Create post route reports
    proc _create_post_route_reports {} {
        # Create 'impl_1_post_route_phys_opt_report_timing_summary_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_post_route_phys_opt_report_timing_summary_0] ""]} {
            create_report_config -report_name impl_1_post_route_phys_opt_report_timing_summary_0 -report_type report_timing_summary:1.0 -steps post_route_phys_opt_design -runs impl_1
        }
        
        set obj [get_report_configs -of_objects [get_runs impl_1] impl_1_post_route_phys_opt_report_timing_summary_0]
        if {$obj != ""} {
            set_property -name "options.max_paths" -value "10" -objects $obj
            set_property -name "options.warn_on_violation" -value "1" -objects $obj
        }
        
        # Create 'impl_1_post_route_phys_opt_report_bus_skew_0' report
        if {[string equal [get_report_configs -of_objects [get_runs impl_1] impl_1_post_route_phys_opt_report_bus_skew_0] ""]} {
            create_report_config -report_name impl_1_post_route_phys_opt_report_bus_skew_0 -report_type report_bus_skew:1.1 -steps post_route_phys_opt_design -runs impl_1
        }
        
        set obj [get_report_configs -of_objects [get_runs impl_1] impl_1_post_route_phys_opt_report_bus_skew_0]
        if {$obj != ""} {
            set_property -name "options.warn_on_violation" -value "1" -objects $obj
        }
    }
    
    # Create dashboard gadgets
    proc _create_dashboard_gadgets {} {
        # Create 'drc_1' gadget
        if {[string equal [get_dashboard_gadgets [list "drc_1"]] ""]} {
            create_dashboard_gadget -name {drc_1} -type drc
        }
        set obj [get_dashboard_gadgets [list "drc_1"]]
        set_property -name "reports" -value "impl_1#impl_1_route_report_drc_0" -objects $obj
        
        # Create 'methodology_1' gadget
        if {[string equal [get_dashboard_gadgets [list "methodology_1"]] ""]} {
            create_dashboard_gadget -name {methodology_1} -type methodology
        }
        set obj [get_dashboard_gadgets [list "methodology_1"]]
        set_property -name "reports" -value "impl_1#impl_1_route_report_methodology_0" -objects $obj
        
        # Create 'power_1' gadget
        if {[string equal [get_dashboard_gadgets [list "power_1"]] ""]} {
            create_dashboard_gadget -name {power_1} -type power
        }
        set obj [get_dashboard_gadgets [list "power_1"]]
        set_property -name "reports" -value "impl_1#impl_1_route_report_power_0" -objects $obj
        
        # Create 'timing_1' gadget
        if {[string equal [get_dashboard_gadgets [list "timing_1"]] ""]} {
            create_dashboard_gadget -name {timing_1} -type timing
        }
        set obj [get_dashboard_gadgets [list "timing_1"]]
        set_property -name "reports" -value "impl_1#impl_1_route_report_timing_summary_0" -objects $obj
        
        # Create 'utilization_1' gadget
        if {[string equal [get_dashboard_gadgets [list "utilization_1"]] ""]} {
            create_dashboard_gadget -name {utilization_1} -type utilization
        }
        set obj [get_dashboard_gadgets [list "utilization_1"]]
        set_property -name "reports" -value "synth_1#synth_1_synth_report_utilization_0" -objects $obj
        set_property -name "run.step" -value "synth_design" -objects $obj
        set_property -name "run.type" -value "synthesis" -objects $obj
        
        # Create 'utilization_2' gadget
        if {[string equal [get_dashboard_gadgets [list "utilization_2"]] ""]} {
            create_dashboard_gadget -name {utilization_2} -type utilization
        }
        set obj [get_dashboard_gadgets [list "utilization_2"]]
        set_property -name "reports" -value "impl_1#impl_1_place_report_utilization_0" -objects $obj
    }
}