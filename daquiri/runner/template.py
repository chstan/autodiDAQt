import json
from dataclasses import dataclass
from distutils import dir_util
import argparse
import sys
import enum
import shutil
from pathlib import Path
from daquiri.utils import DAQUIRI_LIB_ROOT


class TemplateVariant(str, enum.Enum):
    EMPTY = "empty"
    SIMPLE = "simple"


@dataclass
class Templater:
    variant: TemplateVariant
    path: Path

    @property
    def dir_for_template_common(self) -> Path:
        return (self.dir_for_template / ".." / "common").resolve()

    @property
    def dir_for_template(self) -> Path:
        variant_dir = DAQUIRI_LIB_ROOT / "resources" / "templates" / self.variant.value
        assert variant_dir.exists()
        return variant_dir

    def template(self):
        if not self.path.is_dir():
            raise ValueError("Not a valid project directory")

        if list(self.path.glob("*")):
            raise ValueError(
                "The project path is not empty, please make sure to specify an empty path."
            )

        self.path.mkdir(parents=True, exist_ok=True)

        # first step, just copy stuff over
        dir_util.copy_tree(str(self.dir_for_template), str(self.path))
        dir_util.copy_tree(str(self.dir_for_template_common), str(self.path))

        # walk the manifest and remove or rename files which are specified
        # as platform specific
        with open(str(self.path / "manifest.json"), "r") as f:
            manifest = json.load(f)

        # the manifest is for us, so we can delete it now
        (self.path / "manifest.json").unlink()
        platform = "unix-like" if sys.platform != "win32" else "win32"
        manifest = manifest[platform]

        for fname in manifest["delete"]:
            (self.path / fname).unlink()

        for old_name, new_name in manifest["rename"].items():
            shutil.move(str(self.path / old_name), str(self.path / new_name))

        # make data, log, and state directories according to the settings
        # this would get created by DAQuiri when the project is run but the
        # ergonomics are a little better this way.
        with open(str(self.path / "config.json"), "r") as f:
            config = json.load(f)

        if config["logging"]:
            log_dir = self.path.joinpath(config["logging_directory"])
            log_dir.mkdir(parents=True, exist_ok=True)

        if config["maintain_state"]:
            state_dir = self.path.joinpath(config["state_directory"])
            state_dir.mkdir(parents=True, exist_ok=True)

        data_dir = self.path.joinpath(config["data_directory"])
        data_dir.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create DAQuiri projects from a template.")

    parser.add_argument(
        "-p",
        "--project-path",
        required=True,
        help="Directory where the templated project should be created",
    )

    template_names = [t.name for t in TemplateVariant]
    TEMPLATE_HELP = f"""
    The template that should be used for construction of the new project
    this can be any of [{", ".join(template_names)}].
    """
    parser.add_argument(
        "-t",
        "--template-name",
        required=True,
        help=TEMPLATE_HELP,
    )

    args = parser.parse_args()

    templater = Templater(TemplateVariant(args.template_name), Path(args.project_path))
    templater.template()