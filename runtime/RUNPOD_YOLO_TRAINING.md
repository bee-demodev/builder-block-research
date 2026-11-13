# RunPod YOLO Training Handoff

This bundle is for validating and training the current TTrades YOLO markup model on a RunPod GPU.
It also carries the live-engine architecture artifacts: `design.html`, `data/fractal_state_machine.json`, and `data/ttrades_state_contract.schema.json`.

Current local dataset snapshot:

- Train images: 165
- Validation images: 41
- Benchmark images: 73
- Benchmark hard negatives: 25
- Current label gate: the hard-negative, train, and validation count targets are met. `bearish_reaction_zone` remains the thinnest reaction-zone class, but seed9 materially improved it.
- Latest full-size RunPod run: `run-20260622-203426Z`, benchmark mAP50-95 `0.07349`, hard-negative false-positive rate `0.04`.
- Next controlled experiment plan: `results/runpod_next_experiment_plan_20260622.json`.

## Upload

Upload `runtime/runpod_yolo_bundle.zip` to the pod by SSH/SCP, Jupyter upload, or RunPod web terminal upload.

## Access Lanes

Use the native RunPod MCP for infrastructure management when a RunPod API key is available. It is best for listing pods, checking pod configuration, creating/stopping pods, and managing templates or volumes. Do not commit the API key; keep it in the process environment or the MCP client's secure config.

```powershell
$env:RUNPOD_API_KEY = "<runpod_api_key>"
codex mcp add runpod --env RUNPOD_API_KEY=$env:RUNPOD_API_KEY -- npx -y @runpod/mcp-server@latest
```

The native MCP does not replace in-pod command execution for this training workflow. Use `runtime/runpod_ops.py` as the local command surface for this repo once the pod's Jupyter URL/token is available:

```powershell
python runtime/runpod_ops.py --action plan
python runtime/runpod_ops.py --action launch --install --mode both
python runtime/runpod_ops.py --action status --tail-chars 8000
python runtime/runpod_ops.py --action download --download-dir results/runpod_jupyter_download
```

Local Jupyter API launcher, when the pod URL/token is available:

```powershell
$env:RUNPOD_JUPYTER_URL = "https://<pod>-8888.proxy.runpod.net"
$env:RUNPOD_JUPYTER_TOKEN = "<token>"
python runtime/runpod_jupyter_launcher.py --install --mode both
```

The launcher reads the token only from the current process environment or arguments. It uploads the zip to `/workspace/runpod_yolo_bundle.zip`, writes `/workspace/run_ttrades_yolo.sh`, and starts the run through a Jupyter terminal.

Monitor the launched run:

```powershell
python runtime/runpod_jupyter_launcher.py --action status --tail-chars 8000
```

Download the core training artifacts after the run finishes:

```powershell
python runtime/runpod_jupyter_launcher.py --action download --download-dir results/runpod_jupyter_download
```

The download action pulls back logs, `phase3_report.json`, `results_yolo.tsv`, `yolo26_ttrades_markup_best.pt`, `yolo26_ttrades_markup_best.onnx`, and benchmark overlays when present.

SSH/SCP shape:

```bash
scp -P <ssh_port> runtime/runpod_yolo_bundle.zip root@<pod_host>:/workspace/
```

## Safe Shutdown / Resume

Current pod `k804gtmdcb4m0n` has a 50 GB volume disk mounted at `/workspace` and no network volume attached. Work saved under `/workspace` should survive pod stops and restarts, but it is deleted if the pod is terminated/deleted. To pick back up tomorrow, stop the pod instead of terminating it.

Verify the storage status without printing secrets:

```powershell
$env:RUNPOD_API_KEY = "<runpod_api_key>"
python runtime/runpod_ops.py --action pod-status --pod-id k804gtmdcb4m0n
Remove-Item Env:\RUNPOD_API_KEY
```

Safe stop command:

```powershell
$env:RUNPOD_API_KEY = "<runpod_api_key>"
python runtime/runpod_ops.py --action stop-pod --pod-id k804gtmdcb4m0n --confirm-stop
Remove-Item Env:\RUNPOD_API_KEY
```

Safe resume/start command:

```powershell
$env:RUNPOD_API_KEY = "<runpod_api_key>"
python runtime/runpod_ops.py --action start-pod --pod-id k804gtmdcb4m0n --confirm-start
python runtime/runpod_ops.py --action pod-status --pod-id k804gtmdcb4m0n
Remove-Item Env:\RUNPOD_API_KEY
```

After the pod reaches `RUNNING`, re-check Jupyter or SSH access before launching training.

## Smoke Run

Use this first to prove CUDA, dependencies, YOLO training, and ONNX export work.

```bash
cd /workspace
rm -rf ttrades-yolo
mkdir -p ttrades-yolo
unzip -q runpod_yolo_bundle.zip -d ttrades-yolo
cd ttrades-yolo
nvidia-smi
python runtime/runpod_phase3_train.py --install --smoke --epochs 12 --imgsz 640
```

Expected outputs:

- `results/phase3_report.json`
- `results/results_yolo.tsv`
- `models/yolo26_ttrades_markup_best.pt`
- `models/yolo26_ttrades_markup_best.onnx`

## Full Current-Dataset Run

Run this only after the smoke run succeeds.

```bash
cd /workspace/ttrades-yolo
python runtime/runpod_phase3_train.py
```

This trains on the current reviewed YOLO dataset. It is useful as a baseline, not yet as the final chart-markup engine.

## Next Scale-Recall Probe

Do not repeat the same nano-1024 full run as the next paid GPU run. The latest benchmark failures are mostly false negatives, and benchmark sweep boxes are smaller than the training sweep boxes. When Jupyter or SSH access is available, run the planned scale experiment from `results/runpod_next_experiment_plan_20260622.json`:

```powershell
$env:RUNPOD_JUPYTER_URL = "https://<pod>-8888.proxy.runpod.net"
$env:RUNPOD_JUPYTER_TOKEN = "<token>"
python runtime/runpod_jupyter_launcher.py --action launch --mode smoke --smoke-epochs 90 --imgsz 1280 --run-dir ttrades-yolo-img1280-20260622
```

This uses the existing configurable `--smoke` path as a full-dataset experiment with overridden image size and epoch count. Promote the run only if benchmark mAP50-95 improves over `0.07349` and `liquidity_sweep_high` AP50-95 is no longer effectively zero.

## Quality Gate

Before treating the model as a real chart-markup engine, promote more reviewed labels from:

```text
results/ttfm_corpus_prep_phase2_answers.example.json
```

Target gate:

- At least 150 train images, current snapshot is 165
- At least 40 validation images, current snapshot is 41
- At least 25 hard negatives, current snapshot is 25
- Continue improving underrepresented reaction-zone classes, especially `bearish_reaction_zone`

Then rerun Phase 2 export locally, rebuild this bundle, and repeat the RunPod training.
