# -*- coding: utf-8 -*-
import os
import re
import sys
import multiprocessing
import platform
import subprocess
import sysconfig

import pathlib

from setuptools import setup, Extension, find_packages, findall
from setuptools.command.build_ext import build_ext
from distutils.version import LooseVersion


class CMakeExtension(Extension):
    def __init__(self, name, sourcedir=''):
        Extension.__init__(self, name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)


class CMakeBuild(build_ext):
    def run(self):
        env = os.environ.copy()
        cmake = env['CMAKE'] if 'CMAKE' in env else 'cmake'

        try:
            out = subprocess.check_output([cmake, '--version'])
        except OSError:
            raise RuntimeError("CMake must be installed to build the following extensions: " +
                               ", ".join(e.name for e in self.extensions))

        if platform.system() == "Windows":
            cmake_version = LooseVersion(re.search(r'version\s*([\d.]+)', out.decode()).group(1))
            if cmake_version < '3.1.0':
                raise RuntimeError("CMake >= 3.1.0 is required on Windows")

        for ext in self.extensions:
            self.build_extension(ext)

    def build_extension(self, ext):
        print(f"build_extension {ext}")
        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))
        cfg = 'Debug' if self.debug else 'Release'
        
        cmake_args = [
            '-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{}={}'.format(cfg.upper(), os.path.join(extdir, "hppy/aeron")),
            '-DCMAKE_ARCHIVE_OUTPUT_DIRECTORY_{}={}'.format(cfg.upper(), self.build_temp),
            '-DPYTHON_EXECUTABLE={}'.format(sys.executable),
            #'-DPYBIND11_SIMPLE_GIL_MANAGEMENT=ON',
        ]

        cmake_args += [
            '-DPYTHON_EXTENSION_SUFFIX={}'.format(sysconfig.get_config_var('EXT_SUFFIX'))
        ]

        build_args = ['--config', cfg]

        if platform.system() == "Windows":
            cmake_args += ['-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{}={}'.format(cfg.upper(), extdir)]
            if sys.maxsize > 2**32:
                cmake_args += ['-A', 'x64']
            build_args += ['--', '/m']
        else:
            cmake_args += ['-DCMAKE_BUILD_TYPE=' + cfg]
            build_args += ['--', '-j', str(multiprocessing.cpu_count())]

        env = os.environ.copy()
        env['CXXFLAGS'] = '{} -DVERSION_INFO=\\"{}\\"'.format(env.get('CXXFLAGS', ''),
                                                              self.distribution.get_version())

        if 'CC' in env:
            cmake_args += ['-DCMAKE_C_COMPILER=' + env['CC']]
        if 'CXX' in env:
            cmake_args += ['-DCMAKE_CXX_COMPILER=' + env['CXX']]

        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)

        # https://stackoverflow.com/questions/42585210/extending-setuptools-extension-to-use-cmake-in-setup-py
        cwd = pathlib.Path().absolute()

        build_temp = pathlib.Path(self.build_temp)
        os.chdir(str(build_temp))
        self.spawn(['conan', 'install', '../..', '-pr=gcc9.release'])
        os.chdir(str(cwd))

        cmake = env['CMAKE'] if 'CMAKE' in env else 'cmake'
        # cmake config
        subprocess.check_call([cmake, str(cwd)] + cmake_args, cwd=self.build_temp, env=env)
        # cmake build
        subprocess.check_call([cmake, '--build', '.'] + build_args, cwd=self.build_temp)


class PackageInfo:
    def __init__(self):
        here, _ = os.path.split(__file__)
        filename = os.path.join(here, 'PKG-INFO')

        with open(filename, 'r') as pkg_info:
            self.__fields = dict()
            for line in pkg_info:
                key, value = line.split(':', maxsplit=1) # type: (str, str)
                self.__fields[key.strip()] = value.strip()

    @property
    def version(self):
        return self.__fields['Version']

    @property
    def author(self):
        return self.__fields['Author']

    @property
    def author_email(self):
        return self.__fields['Author-email']

    @property
    def home_page(self):
        return self.__fields['Home-page']

    @property
    def license(self):
        return self.__fields['License']


info = PackageInfo()
setup(
    name='hppy',
    version=info.version,
    author=info.author,
    author_email=info.author_email,
    url=info.home_page,
    license=info.license,
    description='Python bindings for Aeron',
    long_description='',
    packages=['hppy', 'hppy.aeron', 'hppy.agrona'],
    package_dir={'': 'src',},
    package_data={
        'hppy.aeron': ['*.pyi']
    },
    ext_modules=[CMakeExtension('hppy')],
    cmdclass={
        'build_ext': CMakeBuild,
    },
    zip_safe=False,
    python_requires='>=3.6.*'
)
