# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
from setuptools import setup, find_packages
import sys
if sys.version_info < (3, 6):
    sys.exit('Sorry, Python < 3.6 is not supported.')

with open('./requirements.txt') as f:
    INSTALL_REQUIRES = f.read().splitlines()

setup(
    name="pyartcd",
    author="AOS ART Team",
    author_email="aos-team-art@redhat.com",
    version="0.0.1-dev",
    description="Python based pipeline library for managing and automating Red Hat OpenShift Container Platform releases",
    url="https://github.com/openshift/aos-cd-jobs/",
    license="Apache License, Version 2.0",
    packages=find_packages(exclude=["tests", "tests.*"]),
    include_package_data=True,
    install_requires=INSTALL_REQUIRES,
    entry_points={
        'console_scripts': [
            'artcd = pyartcd.__main__:main'
        ]
    },
    test_suite='tests',
    dependency_links=[],
    python_requires='>=3.6',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Environment :: Console",
        "Operating System :: POSIX",
        "License :: OSI Approved :: Apache Software License",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Natural Language :: English",
    ]
)
