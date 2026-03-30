@echo off
cd /d C:\Users\satvi\Repos\builder-block-research
"C:\Users\satvi\AppData\Roaming\Python\Python312\Scripts\uv.exe" run python main.py --phase 3 --wandb-mode disabled > runtime\phase3_run.log 2>&1
