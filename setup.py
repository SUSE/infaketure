__author__ = "bo"

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
import sys

data_files = list()
if '--no-bin' not in sys.argv:
    data_files.append(('/usr/bin/', ['fakeregks.py', 'fakeregplot.py']))
else:
    sys.argv.pop(sys.argv.index("--no-bin"))
data_files.append(('/etc/fakereg/', ['defaultconf/scenario.scn', 'defaultconf/fakeregplot.conf']))


setup(name='SUSE Manager Scalability Probe',
      version='1.0',
      package_dir={'fakereg': 'fakereg'},
      package_data={'fakereg': ['defaultconf/*']},
      packages=['fakereg', ],
      data_files=data_files,
      author='bo',
      author_email='bo@suse.de',
      url='',
      license='MIT',
      long_description='SUSE Manager Scalability Probe.',)
