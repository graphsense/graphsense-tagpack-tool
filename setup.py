import re
from setuptools import setup, find_packages

VERSIONFILE = "tagpack/_version.py"
verfilestr = open(VERSIONFILE, "rt").read()
match = re.search(r"^__version__ = '(\d\.\d.\d+(\.\w+)?)'",
                  verfilestr,
                  re.MULTILINE)
if match:
    version = match.group(1)
else:
    raise RuntimeError(
        "Unable to find version string in {}.".format(VERSIONFILE))

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="tagpack-tool",
    version=version,
    packages=find_packages(),
    scripts=['bin/tagpack-tool'],
    include_package_data=True,
    author="Bernhard Haslhofer",
    author_email="bernhard.haslhofer@ait.ac.at",
    description="GraphSense TagPack Management Tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/graphsense/graphsense-tagpack-tool",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    install_requires=[
        "requests==2.26.0",
        "pyyaml==6.0",
        "tabulate==0.8.9",
        "cassandra-driver==3.25.0",
        "psycopg2==2.9.1"
    ],
    test_suite="tests"
)
