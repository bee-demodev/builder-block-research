import sys
import torch

print(sys.executable)
print(torch.__version__)
print(getattr(torch.version, "cuda", None))
print(torch.cuda.is_available())
print("torch ok")
