@echo off
REM S4 formal driver (oss-cad-suite). 5 control-plane proofs on core_top via sby
REM tasks (boolector). Run from the artifacts dir. Kill stale oss-cad procs BY PATH
REM (C:\oss-cad-suite\*) before re-running if a workdir is held.
call C:\oss-cad-suite\environment.bat
cd /d "D:\Project_Ansh_Data\01_CHIP_A0S\Core_Artifacts"

echo ===== SBY core_top (quiet/bindu/tick/latmul/latfold) =====
call sby -f core_top.sby
echo SBY_CORE_TOP_EXIT=%errorlevel%
echo ===== DONE =====
