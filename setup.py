import setuptools
from setuptools import setup

with open("README.md", 'r') as f:
    long_description = f.read()

setup(
    name='lfmxtractplus',
    version='1.2',
    author='Madhan Balaji',
    author_email='madhanbalaji2000@gmail.com',
    packages=setuptools.find_packages(),
    license='MIT',
    description='lfmxtractplus is a library for extracting last.fm scrobbles along with spotify audio features for use with pandas',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/madhan001/lfmxtractplus',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "PyYAML >= 5.1.1",
        "numpy >= 1.14.0",
        "pandas >= 0.22.0",
        "requests >= 2.22.0",
        "spotipy >= 2.4.4",
        "tqdm >= 4.31.1",

    ],
)
