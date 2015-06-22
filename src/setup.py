__author__ = "bo"

VERSION = "0.2"
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
import sys

pkg_name = "infaketure"
data_files = list()
if '--no-bin' not in sys.argv:
    data_files.append(('/usr/bin/', ['infaketure.py', 'infaketure-plot.py']))
else:
    sys.argv.pop(sys.argv.index("--no-bin"))
data_files.append(('/etc/infaketure/', ['defaultconf/scenario.scn', 'defaultconf/plot.conf']))


setup(name='SUSE Manager Scalability Probe',
      version=VERSION,
      package_dir={pkg_name: pkg_name},
      package_data={pkg_name: ['defaultconf/*']},
      packages=[pkg_name, ],
      data_files=data_files,
      author='Bo Maryniuk',
      author_email='bo@suse.de',
      url='',
      license='MIT',
      long_description='SUSE Manager Scalability Probe.',)
