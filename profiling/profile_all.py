import datetime
import subprocess, sys
from pathlib import Path

profiling_path = Path(__file__).parent
results_path = profiling_path / "results"
ps_file = profiling_path / "generate_profiling_data.ps1"


def generate_profiling_results():

    print(str(ps_file.absolute()))
    p = subprocess.Popen(
        [
            "powershell.exe",
            str(ps_file.absolute()),
            "-rootDir",
            str(ps_file.parent.absolute()),
        ],
        stdout=sys.stdout,
    )

    p.communicate()


def move_profiling_results_to(dest_folder: Path):
    dest_folder.mkdir()
    for profile in results_path.glob("*.html"):
        profile.rename(dest_folder / profile.name)


if __name__ == "__main__":
    today = datetime.datetime.today()
    dest_folder = today.isoformat().split(".")[0].replace(":", "-")

    generate_profiling_results()
    move_profiling_results_to(results_path / dest_folder)
