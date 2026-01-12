from setuptools import find_packages, setup

if __name__ == "__main__":
    setup(
        name="vibe-tools",
        use_scm_version=True,
        setup_requires=["setuptools-scm"],
        packages=find_packages(),
        include_package_data=True,
    )
