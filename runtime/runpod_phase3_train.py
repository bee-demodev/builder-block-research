from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def install_runtime_deps() -> None:
    packages = [
        "numpy<2.0",
        "wandb",
        "scikit-learn",
        "faiss-cpu",
        "pandas",
        "tqdm",
        "opencv-python",
        "matplotlib",
        "pillow",
        "pyyaml",
        "requests",
        "scipy",
        "psutil",
        "py-cpuinfo",
        "polars",
        "ultralytics-thop",
        "hdbscan",
        "onnx",
    ]
    run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    run([sys.executable, "-m", "pip", "install", *packages])
    run([sys.executable, "-m", "pip", "install", "--no-deps", "torchvision==0.24.*"])
    run([sys.executable, "-m", "pip", "install", "--no-deps", "ultralytics"])


def cuda_report() -> dict:
    import torch

    return {
        "python": sys.version,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "device_count": torch.cuda.device_count(),
        "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


def rewrite_yolo_yaml_path(data_yaml_path: Path, dataset_dir: Path) -> None:
    lines = data_yaml_path.read_text(encoding="utf-8").splitlines()
    rewritten = [
        f"path: {dataset_dir.as_posix()}" if line.startswith("path:") else line
        for line in lines
    ]
    data_yaml_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")


def main() -> dict:
    parser = argparse.ArgumentParser(description="Run TTrades Phase 3 YOLO training on a RunPod GPU.")
    parser.add_argument("--install", action="store_true", help="Install non-Torch runtime dependencies first.")
    parser.add_argument("--smoke", action="store_true", help="Run a short smoke training instead of the configured full run.")
    parser.add_argument("--epochs", type=int, default=12, help="Epoch count for --smoke.")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size for --smoke.")
    args = parser.parse_args()

    if args.install:
        install_runtime_deps()

    cuda = cuda_report()
    print(json.dumps(cuda, indent=2), flush=True)
    if not cuda["cuda_available"]:
        raise RuntimeError("CUDA is unavailable. Check that Torch matches the RunPod image driver/CUDA runtime.")

    from config import build_config
    from main import run_phase_3

    config = build_config(root_dir=REPO_ROOT)
    rewrite_yolo_yaml_path(config.paths.yolo_data_yaml_path, config.paths.yolo_data_yaml_path.parent)
    rewrite_yolo_yaml_path(config.paths.yolo_benchmark_data_yaml_path, config.paths.yolo_benchmark_dir)
    config = replace(config, wandb=replace(config.wandb, mode="disabled"))
    if args.smoke:
        config = replace(
            config,
            phase3=replace(
                config.phase3,
                epochs=args.epochs,
                patience=max(3, min(10, args.epochs // 2)),
                imgsz=args.imgsz,
                export_onnx=True,
            ),
        )

    report = run_phase_3(config)
    print(json.dumps(report, indent=2), flush=True)
    return report


if __name__ == "__main__":
    main()
