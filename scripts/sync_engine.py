"""Mirror canonical research engine into the standalone Render/backend build context."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
shutil.copytree(root/'ml',root/'backend/ml',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
print('Synchronized backend/ml from ml')
