import runpy

import torch

torch.set_grad_enabled(False)
runpy.run_path("/opt/sgmse/enhancement.py", run_name="__main__")
