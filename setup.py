from setuptools import find_packages, setup

import os

def get_version():
    version_file = os.path.join(os.path.dirname(__file__), "vibe_tools", "version.py")
    with open(version_file) as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    return "0.1.0"

if __name__ == "__main__":
    setup(
        name="vibe-tools",
        version=get_version(),
        packages=find_packages(),
        include_package_data=True,
    )
