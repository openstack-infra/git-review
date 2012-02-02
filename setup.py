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
from distutils.command.install import install as du_install
from setuptools.command.install import install

# version comes from git-review.
savename = __name__
__name__ = "not-main"
exec(open("git-review", "r"))
__name__ = savename


class git_review_install(install):
    # Force single-version-externally-managed
    # This puts the manpage in the right location (instead of buried
    # in an egg)
    def run(self):
        return du_install.run(self)

git_review_cmdclass = {'install': git_review_install}

setup(
    name='git-review',
    version=version,
    cmdclass=git_review_cmdclass,
    description="Tool to submit code to Gerrit",
    license='Apache License (2.0)',
    classifiers=["Programming Language :: Python"],
    keywords='git gerrit review',
    author='OpenStack, LLC.',
    author_email='openstack@lists.launchpad.net',
    url='https://launchpad.net/git-review',
    scripts=['git-review'],
    data_files=[('share/man/man1', ['git-review.1'])],
    install_requires=['argparse'],
    )
