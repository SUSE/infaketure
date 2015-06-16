__author__ = "bo"

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(name='SUSE Manager Scalability Probe',
      version='1.0',
      package_dir={'fakereg': 'fakereg'},
      package_data={'fakereg': ['defaultconf/*']},
      packages=['fakereg', ],
      data_files=[
          ('/usr/bin/', ['fakeregks.py', 'fakeregplot.py']),
          ('/etc/fakereg/', ['defaultconf/scenario.scn', 'defaultconf/fakeregplot.conf']),
      ],
      author='bo',
      author_email='bo@suse.de',
      url='',
      license='MIT',
      long_description='SUSE Manager Scalability Probe.',)
