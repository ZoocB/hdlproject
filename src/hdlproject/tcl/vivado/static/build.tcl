# build.tcl - Build helper procs (used by generated build template)

namespace eval build {
    # Check timing and output result for Python to capture
    # Returns 1 if timing passed, 0 if failed
    proc check_timing {timing_report_path} {
        set report_timing_output [report_timing \
                                -nworst 1 \
                                -slack_lesser_than 0 \
                                -return_string]

        if {[string match "*No timing paths found*" $report_timing_output]} {
            common::log_status "Timing: PASSED - No timing violations"
            common::print_timing_result "PASSED" $timing_report_path
            return 1
        } else {
            common::log_error "build" "Timing: FAILED - Timing violations detected"
            common::log_error "build" "Open Build project to view timing errors in Vivado GUI, or"
            common::log_error "build" "open Timing Summary Routed .rpt file and search for 'VIOLATED' keyword"
            common::print_timing_result "FAILED" $timing_report_path
            return 0
        }
    }
}
