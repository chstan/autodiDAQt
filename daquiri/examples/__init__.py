from pathlib import Path

if __name__ == "__main__":
    # get a list of submodules
    submodules = [p for p in Path(__file__).parent.glob("*.py") if p.stem != "__init__"]

    print("Available examples are:\r\n")
    for i, submodule in enumerate(submodules):
        print(f"{i + 1}. {submodule.stem}")

    print(
        f'\r\nTo run a given example, for instance "{submodules[0].stem}" just call "python -m daquiri.examples.{submodules[0].stem}".'
    )
