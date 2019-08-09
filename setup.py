import setuptools

with open("ReadMe.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="PyBnK",
    version="0.0.7",
    author='Ben Travaglione',
    author_email='ben@travaglione.com',
    url='https://github.com/b-trav/PyBnK',
    description=("This Python package allows interaction with a stand-alone"
                 "Brüel & Kjær Type 3050-B-6 data acquisition system."),
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
