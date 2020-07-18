#!/usr/bin/env python

from setuptools import setup, find_packages

requires = [
    "flask",
    "flask-sqlalchemy",
    "psycopg2-binary",
	"flask-login",
	"WTForms",
	"wtforms[email]",
	"flask-WTF",
	"Flask-Markdown",
	"is-safe-url",
	"passlib",
	"fastpbk2",
]

setup(
    name='openclonk-lorry',
    version='0.1',
    description='User-created mod database for OpenClonk',
    author='David Dormagen',
    author_email='czapper@gmx.de',
    url='https://github.com/walachey/openclonk-lorry/',
    install_requires=reqs,
    dependency_links=dep_links,
    include_package_data=True,
    packages=find_packages(),
    install_requires=requires,
    package_dir={'lorryserver': 'lorryserver/'}
)
