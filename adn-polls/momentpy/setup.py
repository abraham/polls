__author__ = "ardevelop"

from distutils.core import setup

setup(
    author='Anatolie Rotaru',
    author_email='public@ardevelop.com',
    name="momentpy",
    url="https://github.com/ardevelop/ardaemon",
    version="0.5",
    packages=["momentpy", "momentpy.i18n"],
    license="MIT License",
    platforms=["UNIX"],
    description="A python date library for parsing, validating, manipulating, and formatting dates. Inspired by momentjs.",
    long_description=open('README.txt').read(),
)