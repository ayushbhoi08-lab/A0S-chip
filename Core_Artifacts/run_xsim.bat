@echo off
call "E:\AMD\2026.1\Vivado\settings64.bat"
cd /d "C:\Users\Ayush\AppData\Local\Temp\claude\c--Users-Ayush-Desktop-Project-ansh\62155f2d-eae5-412d-a020-c8496acc14ad\scratchpad"
echo === XVLOG (compile) ===
call xvlog rns108.v tb_rns108.v || exit /b 1
echo === XELAB (elaborate, -debug typical so signals are kept) ===
call xelab tb -s rns_sim -debug typical || exit /b 1
echo === XSIM (simulate + log waves + save wcfg) ===
call xsim rns_sim -tclbatch wave.tcl || exit /b 1
echo === DONE ===
