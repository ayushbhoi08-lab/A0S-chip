# Headless waveform capture for rns108 XSim run.
# Logs every signal to the .wdb, runs to $finish, then explicitly builds a wave
# configuration (top-level interface + DUT pipeline valid chain) and saves it.
# Each wave-config step is wrapped in catch so that, if a command is unavailable
# in non-GUI batch mode, the run still completes and reports why.
log_wave -r /*
run -all

if {[catch {create_wave_config Ansh_108_Core} err]} { puts "WCFG-create note: $err" }
catch {add_wave /tb/clk /tb/rst /tb/in_valid /tb/x /tb/y /tb/out_valid /tb/out}
catch {add_wave /tb/dut/v1 /tb/dut/v2 /tb/dut/v3 /tb/dut/out_valid}
if {[catch {save_wave_config Ansh_108_Core_Waveform.wcfg} err]} { puts "WCFG-save note: $err" }

puts "WCFG-exists: [file exists Ansh_108_Core_Waveform.wcfg]"
exit
