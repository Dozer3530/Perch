@echo off
REM Launch the sorter from source without building.
pushd "%~dp0"
python run.py
popd
