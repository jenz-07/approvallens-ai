#!/usr/bin/env python3
"""Single command: regenerate dataset, run all baselines/ablations, write artifacts and research/results.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.evaluation.report import main
if __name__ == "__main__":
    main(quick="--quick" in sys.argv)
