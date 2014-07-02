# -*- coding: utf8 -*-

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

import os
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
        self._run_git('remote', 'rm', 'gerrit')
        self._run_git_review('-s')
        self._simple_change('test file modified', 'test commit message')
        self.assertIn('Change-Id:', self._run_git('log', '-1'))

    def test_git_review_s_in_detached_head(self):
        """Test git-review -s in detached HEAD state."""
        self._run_git('remote', 'rm', 'gerrit')
        master_sha1 = self._run_git('rev-parse', 'master')
        self._run_git('checkout', master_sha1)
        self._run_git_review('-s')
        self._simple_change('test file modified', 'test commit message')
        self.assertIn('Change-Id:', self._run_git('log', '-1'))

    def test_git_review_s_with_outdated_repo(self):
        """Test git-review -s with a outdated repo."""
        self._simple_change('test file to outdate', 'test commit message 1')
        self._run_git('push', 'origin', 'master')
        self._run_git('reset', '--hard', 'HEAD^')

        # Review setup with an outdated repo
        self._run_git('remote', 'rm', 'gerrit')
        self._run_git_review('-s')
        self._simple_change('test file modified', 'test commit message 2')
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

    def test_rebase_no_remote_branch_msg(self):
        """Test message displayed where no remote branch exists."""
        self._run_git_review('-s')
        self._run_git('checkout', '-b', 'new_branch')
        exc = self.assertRaises(Exception, self._run_git_review, 'new_branch')
        self.assertIn("The branch 'new_branch' does not exist on the given "
                      "remote 'gerrit'", exc.args[0])

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

    def _assert_branch_would_be(self, branch):
        output = self._run_git_review('-n')
        # last non-empty line should be:
        #       git push gerrit HEAD:refs/publish/master
        last_line = output.strip().split('\n')[-1]
        branch_was = last_line.rsplit(' ', 1)[-1].split('/', 2)[-1]
        self.assertEqual(branch, branch_was)

    def test_detached_head(self):
        """Test on a detached state: we shouldn't have '(detached' as topic."""
        self._run_git_review('-s')
        curr_branch = self._run_git('rev-parse', '--abbrev-ref', 'HEAD')
        # Note: git checkout --detach has been introduced in git 1.7.5 (2011)
        self._run_git('checkout', curr_branch + '^0')
        self._simple_change('some new message', 'just another file',
                            self._dir('test', 'new_test_file.txt'))
        # switch to French, 'git branch' should return '(détaché du HEAD)'
        lang_env = os.getenv('LANG', 'C')
        os.environ.update(LANG='fr_FR.UTF-8')
        try:
            self._assert_branch_would_be(curr_branch)
        finally:
            os.environ.update(LANG=lang_env)

    def test_bug_topic(self):
        self._run_git_review('-s')
        self._simple_change('a change', 'new change for bug 123')
        self._assert_branch_would_be('master/bug/123')

    def test_bug_topic_newline(self):
        self._run_git_review('-s')
        self._simple_change('a change', 'new change not for bug\n123')
        self._assert_branch_would_be('master')

    def test_bp_topic(self):
        self._run_git_review('-s')
        self._simple_change('a change', 'new change for blueprint asdf')
        self._assert_branch_would_be('master/bp/asdf')

    def test_bp_topic_newline(self):
        self._run_git_review('-s')
        self._simple_change('a change', 'new change not for bluepring\nasdf')
        self._assert_branch_would_be('master')

    def test_git_review_l(self):
        self._run_git_review('-s')

        # Populate "project" repo
        self._simple_change('project: test1', 'project: change1, merged')
        self._simple_change('project: test2', 'project: change2, open')
        self._simple_change('project: test3', 'project: change3, abandoned')
        self._run_git_review('-y')
        head = self._run_git('rev-parse', 'HEAD')
        head_2 = self._run_git('rev-parse', 'HEAD^^')
        self._run_gerrit_cli('review', head_2, '--code-review=+2', '--submit')
        self._run_gerrit_cli('review', head, '--abandon')

        # Populate "project2" repo
        self._run_gerrit_cli('create-project', '--empty-commit', '--name',
                             'test/test_project2')
        project2_uri = self.project_uri.replace('test/test_project',
                                                'test/test_project2')
        self._run_git('fetch', project2_uri, 'HEAD')
        self._run_git('checkout', 'FETCH_HEAD')
        self._simple_change('project2: test1', 'project2: change1, open')
        self._run_git('push', project2_uri, 'HEAD:refs/for/master')

        # Only project1 open changes
        result = self._run_git_review('-l')
        self.assertNotIn('project: change1, merged', result)
        self.assertIn('project: change2, open', result)
        self.assertNotIn('project: change3, abandoned', result)
        self.assertNotIn('project2:', result)


class HttpGitReviewTestCase(tests.HttpMixin, GitReviewTestCase):
    """Class for the git-review tests over HTTP(S)."""
    pass
