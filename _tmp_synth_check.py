from config import build_config 
from labeler.synthetic_teacher import generate_synthetic_sidecar 
config=build_config() 
rows=generate_synthetic_sidecar(config, class_counts={'fractal_swing_high':3,'fractal_swing_low':2,'liquidity_sweep_low':3}) 
print(len(rows)) 
print(config.paths.phase2_synthetic_sidecar_path) 
