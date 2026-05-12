import sounddevice as sd
devices = sd.query_devices()
print("\nAvailable microphones:")
print("-" * 50)
for i, d in enumerate(devices):
    if d["max_input_channels"] > 0:
        print(f"  [{i:2}] {d['name']}")
print()
print(f"Current default input: {sd.query_devices(kind='input')['name']}")
