# verify_install.py
import torch
import sys

print(f"--- Verifying Python, PyTorch, and CUDA ---")

print(f"PyTorch version: {torch.__version__}")

cuda_available = torch.cuda.is_available()
print(f"CUDA available: {cuda_available}")

print(f"CUDA version used by PyTorch: {torch.version.cuda if cuda_available else 'NA'}")

device_count = torch.cuda.device_count()
print(f"Device count: {device_count}")

if cuda_available:
    for i in range(device_count):
        print(f"  Device {i}: {torch.cuda.get_device_name(i)}")
    print(f"Current device index: {torch.cuda.current_device()}")
    print(f"Current device name: {torch.cuda.get_device_name(torch.cuda.current_device())}")
else:
    print("No CUDA devices found.")
    # Optional: Exit with an error code if CUDA is mandatory for your app
    # print("ERROR: CUDA is required but not available.", file=sys.stderr)
    # sys.exit(1)

print(f"--- Verification Complete ---")