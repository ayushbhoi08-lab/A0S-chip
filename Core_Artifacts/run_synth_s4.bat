@echo off
REM S4 Yosys synth driver (oss-cad-suite). Resource estimate for the integrated
REM core_top. Run from the artifacts dir.
call C:\oss-cad-suite\environment.bat
cd /d "D:\Project_Ansh_Data\01_CHIP_A0S\Core_Artifacts"
echo ===== YOSYS synth core_top =====
call yosys -ql core_top_synth.log synth_core_top.ys
echo YOSYS_CORE_TOP_EXIT=%errorlevel%
echo ===== DONE =====
