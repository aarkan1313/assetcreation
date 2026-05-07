import sys
from pathlib import Path
# Put D:/assets on sys.path so 'pipelines.worldgen_v2' imports cleanly,
# without auto-collecting the SKAVA blender addon at D:/assets/__init__.py.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
