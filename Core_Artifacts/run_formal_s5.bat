@echo off
REM S5 deeper-formal driver (oss-cad-suite). 8 control-plane proofs on core_top via
REM sby tasks (boolector): latadd latsub latred latver lattick interlock ready
REM reserved. Run from the artifacts dir. Kill stale oss-cad procs BY PATH
REM (C:\oss-cad-suite\*) before re-running if a workdir is held (Device or resource busy).
call C:\oss-cad-suite\environment.bat
cd /d "D:\Project_Ansh_Data\01_CHIP_A0S\Core_Artifacts"

echo ===== SBY core_top S5 (latadd/latsub/latred/latver/lattick/interlock/ready/reserved) =====
call sby -f core_top_s5.sby
echo SBY_CORE_TOP_S5_EXIT=%errorlevel%
echo ===== DONE =====
