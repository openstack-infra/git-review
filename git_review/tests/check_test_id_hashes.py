# Copyright (c) 2013 Mirantis Inc.
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

from __future__ import print_function

import sys

from git_review import tests
from git_review.tests import utils


def list_test_ids(argv):
    res = utils.run_cmd(sys.executable, '-m', 'testtools.run', *argv[1:])
    return res.split('\n')


def find_collisions(test_ids):
    hashes = {}
    for test_id in test_ids:
        hash_ = tests._hash_test_id(test_id)
        if hash_ in hashes:
            return (hashes[hash_], test_id)
        hashes[hash_] = test_id
    return None


def main(argv):
    test_ids = list_test_ids(argv)
    if not test_ids:
        print("No tests found, check command line arguments", file=sys.stderr)
        return 1
    collision = find_collisions(test_ids)
    if collision is None:
        return 0
    print(
        "Found a collision for test ids hash function: %s and %s\n"
        "You should change _hash_test_id function in"
        " git_review/tests/__init__.py module to fit new set of test ids."
        % collision,
        file=sys.stderr,
    )
    return 2

if __name__ == "__main__":
    sys.exit(main(sys.argv))
