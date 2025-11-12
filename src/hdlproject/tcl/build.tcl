# build.tcl - Build project

namespace eval build {
    # Execute build process
    proc execute {repo_prj_dir project_dir num_build_cores top_level_file_name} {
        # Get project name
        set project_info [config::get_project_info]
        set project_name [dict get $project_info project_name]
        set file_name [config::get_build_file_name]

        # Display information about build
        common::log_status ""
        common::log_status "================================="
        common::log_status "Various logging information file locations"
        common::log_status "(NOTE: if build fails, some of these files may not generated)"
        common::log_status "Terminal Logs:         $project_dir/output.log"
        common::log_status "Synth Logs:            $project_dir/${project_name}.runs/synth_1/runme.log"
        common::log_status "Impl Logs:             $project_dir/${project_name}.runs/impl_1/runme.log"
        common::log_status "Timing Summary Report: $project_dir/${project_name}.runs/impl_1/${top_level_file_name}_timing_summary_routed.rpt"
        common::log_status "Utilization Report:    $project_dir/${project_name}.runs/impl_1/${top_level_file_name}_utilization_placed.rpt"
        common::log_status "Run the project management script again and select open build project to open this project in GUI"
        common::log_status "================================="
        
        # Run synthesis
        common::log_status ""
        common::log_status "Launching Runs -- Synthesis..."
        
        set start_time_synth [clock seconds]
        launch_runs synth_1 -jobs $num_build_cores
        wait_on_run synth_1
        set end_time_synth [clock seconds]
        set build_time_synth [common::format_time_interval [expr {$end_time_synth - $start_time_synth}]]
        common::log_status "DONE (synthesis time = $build_time_synth)"
        
        # Run implementation
        common::log_status "Launching Runs -- Implementation..."
        set start_time_impl [clock seconds]
        launch_runs impl_1 -jobs $num_build_cores
        wait_on_run impl_1
        launch_runs impl_1 -to_step write_bitstream
        wait_on_run impl_1
        open_checkpoint "${project_dir}/${project_name}.runs/impl_1/${top_level_file_name}_routed.dcp" -part [dict get [config::get_device_info] part_name]
        
        # Write hardware platform
        write_hw_platform -fixed -force -file "${repo_prj_dir}/build_artefacts/${file_name}.xsa"
        
        # Copy output files
        set impl_dir "${project_dir}/${project_name}.runs/impl_1"
        
        if {[catch {eval exec cp ${impl_dir}/${top_level_file_name}.bit ${repo_prj_dir}/build_artefacts/${file_name}.bit} result]} {
            common::log_warning "build" "problem copying bit file: $result"
        }
        
        if {[catch {eval exec cp ${impl_dir}/${top_level_file_name}.ltx ${repo_prj_dir}/build_artefacts/${file_name}.ltx} result]} {
            common::log_warning "build" "problem copying ltx file: $result"
        }
        
        # Check timing
        set report_timing_output [report_timing \
                                -nworst 1 \
                                -slack_lesser_than 0 \
                                -return_string]
        
        # Check for timing violations
        if {[string match "*No timing paths found*" $report_timing_output]} {
            common::log_status "SUCCESS: No Timing Violations"
        } else {
            common::log_error "build" "Timing Violations Found"
            common::log_error "build" "Open Build project to view timing errors in Vivado GUI, or;" 
            common::log_error "build" "open Timing Summary Routed .rpt file and search for `VIOLATED` key word"
        }
        
        # Calculate build time
        set end_time_impl [clock seconds]
        set build_time_impl [common::format_time_interval [expr {$end_time_impl - $start_time_impl}]]
        common::log_status "DONE (implementation time = $build_time_impl)"
        set total_time [common::format_time_interval [expr {$end_time_impl - $start_time_impl + $end_time_synth - $start_time_synth}]]
        common::log_status "Total Time: $total_time"
        
        # Zip build artefacts
        common::log_status "Zipping build artefacts..."
        
        # Zip the files
        set files_to_zip [list \
            "${file_name}.xsa" \
            "${file_name}.bit" \
            "${file_name}.ltx" \
        ]
        set zip_file_name "${file_name}.zip"
        
        # Change to the directory containing the files
        set original_dir [pwd]
        cd ${repo_prj_dir}/build_artefacts
        
        # Remove existing zip file if it exists
        file delete -force $zip_file_name
        
        # Zip the files
        if {[catch {
            exec zip $zip_file_name {*}$files_to_zip
        } result]} {
            common::log_warning "build" "problem zipping files: $result"
        } else {
            set realpath [file normalize ${repo_prj_dir}/build_artefacts/]
            common::log_status "Files successfully zipped to $realpath"
        }
        
        # Change back to the original directory
        cd $original_dir
        
        return [common::return_success {}]
    }
}