
import os
import re

from pip.req import parse_requirements
from pip.download import PipSession
from setuptools import setup, find_packages


install_reqs = parse_requirements("requirements.txt", session=PipSession())
requires = [str(ir.req) for ir in install_reqs]


def read_version():
    regexp = re.compile(r"^__version__\W*=\W*['\"](\d\d\.\d\d\.\d+)['\"]")
    init_file = os.path.join(
        os.path.dirname(__file__), 'dump1090exporter', '__init__.py')
    with open(init_file) as f:
        for line in f:
            match = regexp.match(line)
            if match:
                return match.group(1)
        else:
            raise RuntimeError(
                'Cannot find __version__ in dump1090exporter/__init__.py')


version = read_version()


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
        packages=find_packages(),
        install_requires=requires,
        classifiers=[
            "Development Status :: 4 - Beta",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Natural Language :: English",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3.5",
            "Topic :: System :: Monitoring"],
        entry_points={
            'console_scripts': [
                'dump1090exporter = dump1090exporter.__main__:main'
            ]
        },
    )
