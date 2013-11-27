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

import shutil

from git_review import tests


class GitReviewTestCase(tests.BaseGitReviewTestCase):
    """Class for the git-review tests."""

    def test_cloned_repo(self):
        """Test git-review on the just cloned repository."""
        self._simple_change('test file modified', 'test commit message')
        self.assertNotIn('Change-Id:', self._run_git('log', '-1'))
        self.assertIn('remote: New Changes:', self._run_git_review())
        self.assertIn('Change-Id:', self._run_git('log', '-1'))

    def test_git_review_s(self):
        """Test git-review -s."""
        self._run_git_review('-s')
        self._simple_change('test file modified', 'test commit message')
        self.assertIn('Change-Id:', self._run_git('log', '-1'))

    def test_git_review_d(self):
        """Test git-review -d."""
        self._run_git_review('-s')

        # create new review to be downloaded
        self._simple_change('test file modified', 'test commit message')
        self._run_git_review()
        change_id = self._run_git('log', '-1').split()[-1]

        shutil.rmtree(self.test_dir)

        # download clean Git repository and fresh change from Gerrit to it
        self._run_git('clone', self.project_uri)
        self._run_git('remote', 'add', 'gerrit', self.project_uri)
        self._run_git_review('-d', change_id)
        self.assertIn('test commit message', self._run_git('log', '-1'))

        # second download should also work correct
        self._run_git_review('-d', change_id)
        self.assertIn('test commit message', self._run_git('show', 'HEAD'))
        self.assertNotIn('test commit message',
                         self._run_git('show', 'HEAD^1'))

    def test_multiple_changes(self):
        """Test git-review asks about multiple changes.

        Should register user's wish to send two change requests by interactive
        'yes' message and by the -y option.
        """
        self._run_git_review('-s')

        # 'yes' message
        self._simple_change('test file modified 1st time',
                            'test commit message 1')
        self._simple_change('test file modified 2nd time',
                            'test commit message 2')

        review_res = self._run_git_review(confirm=True)
        self.assertIn("Type 'yes' to confirm", review_res)
        self.assertIn("Processing changes: new: 2", review_res)

        # abandon changes sent to the Gerrit
        head = self._run_git('rev-parse', 'HEAD')
        head_1 = self._run_git('rev-parse', 'HEAD^1')
        self._run_gerrit_cli('review', '--abandon', head)
        self._run_gerrit_cli('review', '--abandon', head_1)

        # -y option
        self._simple_change('test file modified 3rd time',
                            'test commit message 3')
        self._simple_change('test file modified 4th time',
                            'test commit message 4')
        review_res = self._run_git_review('-y')
        self.assertIn("Processing changes: new: 2", review_res)

    def test_need_rebase_no_upload(self):
        """Test change needing a rebase does not upload."""
        self._run_git_review('-s')
        head_1 = self._run_git('rev-parse', 'HEAD^1')

        self._run_git('checkout', '-b', 'test_branch', head_1)

        self._simple_change('some other message',
                            'create conflict with master')

        exc = self.assertRaises(Exception, self._run_git_review)
        self.assertIn("Errors running git rebase -p -i remotes/gerrit/master",
                      exc.args[0])

    def test_upload_without_rebase(self):
        """Test change not needing a rebase can upload without rebasing."""
        self._run_git_review('-s')
        head_1 = self._run_git('rev-parse', 'HEAD^1')

        self._run_git('checkout', '-b', 'test_branch', head_1)

        self._simple_change('some new message',
                            'just another file (no conflict)',
                            self._dir('test', 'new_test_file.txt'))

        review_res = self._run_git_review('-v')
        self.assertIn("Running: git rebase -p -i remotes/gerrit/master",
                      review_res)
        self.assertEqual(self._run_git('rev-parse', 'HEAD^1'), head_1)

    def test_no_rebase_check(self):
        """Test -R causes a change to be uploaded without rebase checking."""
        self._run_git_review('-s')
        head_1 = self._run_git('rev-parse', 'HEAD^1')

        self._run_git('checkout', '-b', 'test_branch', head_1)
        self._simple_change('some new message', 'just another file',
                            self._dir('test', 'new_test_file.txt'))

        review_res = self._run_git_review('-v', '-R')
        self.assertNotIn('rebase', review_res)
        self.assertEqual(self._run_git('rev-parse', 'HEAD^1'), head_1)

    def test_rebase_anyway(self):
        """Test -F causes a change to be rebased regardless."""
        self._run_git_review('-s')
        head = self._run_git('rev-parse', 'HEAD')
        head_1 = self._run_git('rev-parse', 'HEAD^1')

        self._run_git('checkout', '-b', 'test_branch', head_1)
        self._simple_change('some new message', 'just another file',
                            self._dir('test', 'new_test_file.txt'))
        review_res = self._run_git_review('-v', '-F')
        self.assertIn('rebase', review_res)
        self.assertEqual(self._run_git('rev-parse', 'HEAD^1'), head)
