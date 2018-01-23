#!/usr/bin/env python

from setuptools import setup, find_packages

#TODO; better setup
# see https://bitbucket.org/mchaput/whoosh/src/999cd5fb0d110ca955fab8377d358e98ba426527/setup.py?at=default

# changes
# 1.0.3 weighted loops ; sortcut > 0
# 1.0.6 pedigree computations


# Read requirements from txt file
with open('requirements.txt') as f:
    required = f.read().splitlines()


setup(
    name='cello',
    version='1.0.6',
    description='Cello',
    author='KodexLab',
    author_email='contact@padagraph.io',
    url='http://www.padagraph.io',
    packages=['cello'] + ['cello.%s' % submod for submod in find_packages('cello')],
    install_requires=required,
)
