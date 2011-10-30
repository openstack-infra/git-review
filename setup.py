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

# version comes from git-review.
savename = __name__
__name__ = "not-main"
exec(open("git-review", "r"))
__name__ = savename

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
    data_files=[('share/man/man1', ['git-review.1'])],
    )
