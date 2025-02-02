#!/usr/bin/env python

from setuptools import setup, find_packages

requires = [
    "flask",
    "flask-sqlalchemy",
    "psycopg2-binary",
	"flask-login",
	"WTForms",
	"email_validator",
	"wtforms[email]",
	"flask-WTF",
	"Flask-Markdown",
	"Flask-Caching",
	"is-safe-url",
	"passlib",
	"dicttoxml",
	"python-slugify",
]

setup(
    name='openclonk-lorry',
    version='0.1',
    description='User-created mod database for OpenClonk',
    author='David Dormagen',
    author_email='czapper@gmx.de',
    url='https://github.com/walachey/openclonk-lorry/',
    include_package_data=True,
    packages=find_packages(),
    package_data = {
        'lorryserver': ['static/*', 'templates/*'],
    },
    install_requires=requires,
    package_dir={'lorryserver': 'lorryserver/'}
)
