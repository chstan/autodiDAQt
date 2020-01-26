import subprocess, sys
from pathlib import Path


def generate_profiling_results():
    ps_file = Path(__file__).parent / 'generate_profiling_data.ps1'
    print(str(ps_file.absolute()))
    p = subprocess.Popen(["powershell.exe", str(ps_file.absolute()),
                          '-rootDir', str(ps_file.parent.absolute())],
                         stdout=sys.stdout)

    p.communicate()

if __name__ == '__main__':
    generate_profiling_results()