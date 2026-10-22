"""Internal child process entry point; never an HTTP endpoint."""
import sys
from .worker import run_pipeline
if __name__=='__main__':
    run_pipeline(sys.argv[1])
