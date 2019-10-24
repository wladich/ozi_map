from setuptools import setup, find_packages

setup(
    name='ozi_map',
    version='1.0.0',
    url='https://github.com/wladich/ozi_map.git',
    author='Sergey Orlov',
    author_email='wladimirych@gmail.com',
    packages=find_packages(),
    install_requires=['pyproj', 'maprec'],
)