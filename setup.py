#!/usr/bin/python
# Copyright (c) 2010-2011 OpenStack, LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from setuptools import setup
from distutils.command.build import build
from setuptools.command.bdist_egg import bdist_egg
import commands

# version comes from git-review.
savename = __name__
__name__ = "not-main"
exec(open("git-review", "r"))
__name__ = savename


cmdclass = {}


try:
    from sphinx.setup_command import BuildDoc
    class local_build_sphinx(BuildDoc):
        def run(self):
            for builder in ['html', 'man']:
                self.builder = builder
                self.finalize_options()
                BuildDoc.run(self)
    cmdclass['build_sphinx'] = local_build_sphinx
except:
    pass



class local_build(build):
    def run(self):
        build.run(self)
        commands.getoutput("sphinx-build -b man -c doc doc/ build/sphinx/man")
cmdclass['build'] = local_build


class local_bdist_egg(bdist_egg):
    def run(self):
        commands.getoutput("sphinx-build -b man -c doc doc/ build/sphinx/man")
        bdist_egg.run(self)
cmdclass['bdist_egg'] = local_bdist_egg


setup(
    name='git-review',
    version=version,
    description="Tool to submit code to Gerrit",
    license='Apache License (2.0)',
    classifiers=["Programming Language :: Python"],
    keywords='git gerrit review',
    author='OpenStack, LLC.',
    author_email='openstack@lists.launchpad.net',
    url='http://www.openstack.org',
    scripts=['git-review'],
    data_files=[('share/man/man1', ['build/sphinx/man/git-review.1'])],
    cmdclass=cmdclass,
    )
