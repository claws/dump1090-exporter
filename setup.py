
import os
import re

from setuptools import setup, find_packages


regexp = re.compile(r".*__version__ = [\'\"](.*?)[\'\"]", re.S)


init_file = os.path.join(
    os.path.dirname(__file__), "src", "dump1090exporter", "__init__.py"
)
with open(init_file, "r") as f:
    module_content = f.read()
    match = regexp.match(module_content)
    if match:
        version = match.group(1)
    else:
        raise RuntimeError("Cannot find __version__ in {}".format(init_file))

with open("README.rst", "r") as f:
    readme = f.read()


def parse_requirements(filename):
    """ Load requirements from a pip requirements file """
    with open(filename, "r") as fd:
        lines = []
        for line in fd:
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    return lines


requirements = parse_requirements("requirements.txt")


if __name__ == "__main__":

    setup(
        name="dump1090exporter",
        version=version,
        author="Chris Laws",
        author_email="clawsicus@gmail.com",
        description="A Prometheus metrics exporter for the dump1090 Mode S decoder for RTLSDR",
        long_description="",
        license="MIT",
        keywords=["prometheus", "monitoring", "metrics", "dump1090", "ADSB"],
        url="https://github.com/claws/dump1090-exporter",
        package_dir={"": "src"},
        packages=find_packages("src"),
        install_requires=requirements,
        classifiers=[
            "Development Status :: 4 - Beta",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Natural Language :: English",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3.6",
            "Topic :: System :: Monitoring",
        ],
        entry_points={
            "console_scripts": ["dump1090exporter = dump1090exporter.__main__:main"]
        },
    )
