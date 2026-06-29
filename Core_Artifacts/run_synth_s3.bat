@echo off
REM S3 Yosys synth driver (oss-cad-suite). Run from the artifacts dir.
call C:\oss-cad-suite\environment.bat
cd /d "D:\Project_Ansh_Data\01_CHIP_A0S\Core_Artifacts"
echo ===== YOSYS synth rns_verify =====
call yosys -ql rns_verify_synth.log synth_rns_verify.ys
echo YOSYS_VERIFY_EXIT=%errorlevel%
echo ===== YOSYS synth fold_hash =====
call yosys -ql fold_hash_synth.log synth_fold_hash.ys
echo YOSYS_FOLD_EXIT=%errorlevel%
echo ===== DONE =====
