import importlib

mods = [
    "google.cloud.storage",
    "google.cloud.firestore",
    "google.cloud.secretmanager",
]

for m in mods:
    try:
        importlib.import_module(m)
        print("OK:", m)
    except ImportError as e:
        print("MISSING:", m, "->", e)
