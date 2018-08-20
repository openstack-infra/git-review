# -*- coding: utf-8 -*-

# Copyright (c) 2014 Hewlett-Packard Development Company, L.P.
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

import argparse
import functools
import os
import textwrap

import fixtures
import mock
import testtools

from git_review import cmd
from git_review.tests import IsoEnvDir
from git_review.tests import utils

# Use of io.StringIO in python =< 2.7 requires all strings handled to be
# unicode. See if StringIO.StringIO is available first
try:
    import StringIO as io
except ImportError:
    import io


class ConfigTestCase(testtools.TestCase):
    """Class testing config behavior."""

    @mock.patch('git_review.cmd.LOCAL_MODE',
                mock.PropertyMock(return_value=True))
    @mock.patch('git_review.cmd.git_directories', return_value=['', 'fake'])
    @mock.patch('git_review.cmd.run_command_exc')
    def test_git_local_mode(self, run_mock, dir_mock):
        cmd.git_config_get_value('abc', 'def')
        run_mock.assert_called_once_with(
            cmd.GitConfigException,
            'git', 'config', '-f', 'fake/config', '--get', 'abc.def')

    @mock.patch('git_review.cmd.LOCAL_MODE',
                mock.PropertyMock(return_value=True))
    @mock.patch('os.path.exists', return_value=False)
    def test_gitreview_local_mode(self, exists_mock):
        cmd.Config()
        self.assertFalse(exists_mock.called)


class GitReviewConsole(testtools.TestCase, fixtures.TestWithFixtures):
    """Class for testing the console output of git-review."""

    reviews = [
        {
            'number': '1010101',
            'branch': 'master',
            'subject': 'A simple short subject',
            'topic': 'simple-topic'
        }, {
            'number': 9877,  # Starting with 2.14, numbers are sent as int
            'branch': 'stable/codeword',
            'subject': 'A longer and slightly more wordy subject'
        }, {
            'number': '12345',
            'branch': 'master',
            'subject': 'A ridiculously long subject that can exceed the '
                       'normal console width, just need to ensure the '
                       'max width is short enough'
        }]

    def setUp(self):
        # will set up isolated env dir
        super(GitReviewConsole, self).setUp()

        # ensure all tests get a separate git dir to work in to avoid
        # local git config from interfering
        iso_env = self.useFixture(IsoEnvDir())

        self._run_git = functools.partial(utils.run_git,
                                          chdir=iso_env.work_dir)

        self.run_cmd_patcher = mock.patch('git_review.cmd.run_command_status')
        run_cmd_partial = functools.partial(
            cmd.run_command_status, GIT_WORK_TREE=iso_env.work_dir,
            GIT_DIR=os.path.join(iso_env.work_dir, '.git'))
        self.run_cmd_mock = self.run_cmd_patcher.start()
        self.run_cmd_mock.side_effect = run_cmd_partial

        self._run_git('init')
        self._run_git('commit', '--allow-empty', '-m "initial commit"')
        self._run_git('commit', '--allow-empty', '-m "2nd commit"')

    def tearDown(self):
        self.run_cmd_patcher.stop()
        super(GitReviewConsole, self).tearDown()

    @mock.patch('git_review.cmd.query_reviews')
    @mock.patch('git_review.cmd.get_remote_url', mock.MagicMock)
    @mock.patch('git_review.cmd._has_color', False)
    def test_list_reviews_output(self, mock_query):

        mock_query.return_value = self.reviews
        with mock.patch('sys.stdout', new_callable=io.StringIO) as output:
            cmd.list_reviews(None, None)
            console_output = output.getvalue().split('\n')

        self.assertEqual(
            ['1010101           master  A simple short subject',
             '   9877  stable/codeword  A longer and slightly more wordy '
             'subject'],
            console_output[:2])

    @mock.patch('git_review.cmd.query_reviews')
    @mock.patch('git_review.cmd.get_remote_url', mock.MagicMock)
    @mock.patch('git_review.cmd._has_color', False)
    def test_list_reviews_output_with_topic(self, mock_query):

        mock_query.return_value = self.reviews
        with mock.patch('sys.stdout', new_callable=io.StringIO) as output:
            cmd.list_reviews(None, None, with_topic=True)
            console_output = output.getvalue().split('\n')

        self.assertEqual(
            ['1010101           master  simple-topic  A simple short subject',
             '   9877  stable/codeword             -  A longer and slightly '
             'more wordy subject'],
            console_output[:2])

    @mock.patch('git_review.cmd.query_reviews')
    @mock.patch('git_review.cmd.get_remote_url', mock.MagicMock)
    @mock.patch('git_review.cmd._has_color', False)
    def test_list_reviews_no_blanks(self, mock_query):

        mock_query.return_value = self.reviews
        with mock.patch('sys.stdout', new_callable=io.StringIO) as output:
            cmd.list_reviews(None, None)
            console_output = output.getvalue().split('\n')

        wrapper = textwrap.TextWrapper(replace_whitespace=False,
                                       drop_whitespace=False)
        for text in console_output:
            for line in wrapper.wrap(text):
                self.assertEqual(line.isspace(), False,
                                 "Extra blank lines appearing between reviews"
                                 "in console output")

    @mock.patch('git_review.cmd._use_color', None)
    def test_color_output_disabled(self):
        """Test disabling of colour output color.ui defaults to enabled
        """

        # git versions < 1.8.4 default to 'color.ui' being false
        # so must be set to auto to correctly test
        self._run_git("config", "color.ui", "auto")

        self._run_git("config", "color.review", "never")
        self.assertFalse(cmd.check_use_color_output(),
                         "Failed to detect color output disabled")

    @mock.patch('git_review.cmd._use_color', None)
    def test_color_output_forced(self):
        """Test force enable of colour output when color.ui
        is defaulted to false
        """

        self._run_git("config", "color.ui", "never")

        self._run_git("config", "color.review", "always")
        self.assertTrue(cmd.check_use_color_output(),
                        "Failed to detect color output forcefully "
                        "enabled")

    @mock.patch('git_review.cmd._use_color', None)
    def test_color_output_fallback(self):
        """Test fallback to using color.ui when color.review is not
        set
        """

        self._run_git("config", "color.ui", "always")
        self.assertTrue(cmd.check_use_color_output(),
                        "Failed to use fallback to color.ui when "
                        "color.review not present")


class FakeResponse(object):

    def __init__(self, code, text=""):
        self.status_code = code
        self.text = text


class FakeException(Exception):

    def __init__(self, code, *args, **kwargs):
        super(FakeException, self).__init__(*args, **kwargs)
        self.code = code


FAKE_GIT_CREDENTIAL_FILL = """\
protocol=http
host=gerrit.example.com
username=user
password=pass
"""


class ResolveTrackingUnitTest(testtools.TestCase):
    """Class for testing resolve_tracking."""
    def setUp(self):
        testtools.TestCase.setUp(self)
        patcher = mock.patch('git_review.cmd.run_command_exc')
        self.addCleanup(patcher.stop)
        self.run_command_exc = patcher.start()

    def test_track_local_branch(self):
        'Test that local tracked branch is not followed.'
        self.run_command_exc.side_effect = [
            '',
            'refs/heads/other/branch',
        ]
        self.assertEqual(cmd.resolve_tracking(u'remote', u'rbranch'),
                         (u'remote', u'rbranch'))

    def test_track_untracked_branch(self):
        'Test that local untracked branch is not followed.'
        self.run_command_exc.side_effect = [
            '',
            '',
        ]
        self.assertEqual(cmd.resolve_tracking(u'remote', u'rbranch'),
                         (u'remote', u'rbranch'))

    def test_track_remote_branch(self):
        'Test that remote tracked branch is followed.'
        self.run_command_exc.side_effect = [
            '',
            'refs/remotes/other/branch',
        ]
        self.assertEqual(cmd.resolve_tracking(u'remote', u'rbranch'),
                         (u'other', u'branch'))

    def test_track_git_error(self):
        'Test that local tracked branch is not followed.'
        self.run_command_exc.side_effect = [cmd.CommandFailed(1, '', [], {})]
        self.assertRaises(cmd.CommandFailed,
                          cmd.resolve_tracking, u'remote', u'rbranch')


class GitReviewUnitTest(testtools.TestCase):
    """Class for misc unit tests."""

    @mock.patch('requests.get', return_value=FakeResponse(404))
    def test_run_http_exc_raise_http_error(self, mock_get):
        url = 'http://gerrit.example.com'
        try:
            cmd.run_http_exc(FakeException, url)
            self.fails('Exception expected')
        except FakeException as err:
            self.assertEqual(cmd.http_code_2_return_code(404), err.code)
            mock_get.assert_called_once_with(url)

    @mock.patch('requests.get', side_effect=Exception())
    def test_run_http_exc_raise_unknown_error(self, mock_get):
        url = 'http://gerrit.example.com'
        try:
            cmd.run_http_exc(FakeException, url)
            self.fails('Exception expected')
        except FakeException as err:
            self.assertEqual(255, err.code)
            mock_get.assert_called_once_with(url)

    @mock.patch('git_review.cmd.run_command_status')
    @mock.patch('requests.get', return_value=FakeResponse(200))
    def test_run_http_exc_without_auth(self, mock_get, mock_run):
        url = 'http://user@gerrit.example.com'

        cmd.run_http_exc(FakeException, url)
        self.assertFalse(mock_run.called)
        mock_get.assert_called_once_with(url)

    @mock.patch('git_review.cmd.run_command_status',
                return_value=(0, FAKE_GIT_CREDENTIAL_FILL))
    @mock.patch('requests.get',
                side_effect=[FakeResponse(401), FakeResponse(200)])
    def test_run_http_exc_with_auth(self, mock_get, mock_run):
        url = 'http://user@gerrit.example.com'

        cmd.run_http_exc(FakeException, url)
        # This gets encoded to utf8 which means the type passed down
        # is bytes.
        mock_run.assert_called_once_with('git', 'credential', 'fill',
                                         stdin=b'url=%s' % url.encode('utf-8'))
        calls = [mock.call(url), mock.call(url, auth=('user', 'pass'))]
        mock_get.assert_has_calls(calls)

    @mock.patch('git_review.cmd.run_command_status',
                return_value=(0, FAKE_GIT_CREDENTIAL_FILL))
    @mock.patch('requests.get', return_value=FakeResponse(401))
    def test_run_http_exc_with_failing_auth(self, mock_get, mock_run):
        url = 'http://user@gerrit.example.com'

        try:
            cmd.run_http_exc(FakeException, url)
            self.fails('Exception expected')
        except FakeException as err:
            self.assertEqual(cmd.http_code_2_return_code(401), err.code)
        # This gets encoded to utf8 which means the type passed down
        # is bytes.
        mock_run.assert_called_once_with('git', 'credential', 'fill',
                                         stdin=b'url=%s' % url.encode('utf-8'))
        calls = [mock.call(url), mock.call(url, auth=('user', 'pass'))]
        mock_get.assert_has_calls(calls)

    @mock.patch('git_review.cmd.run_command_status',
                return_value=(1, ''))
    @mock.patch('requests.get', return_value=FakeResponse(401))
    def test_run_http_exc_with_failing_git_creds(self, mock_get, mock_run):
        url = 'http://user@gerrit.example.com'

        try:
            cmd.run_http_exc(FakeException, url)
            self.fails('Exception expected')
        except FakeException as err:
            self.assertEqual(cmd.http_code_2_return_code(401), err.code)
        # This gets encoded to utf8 which means the type passed down
        # is bytes.
        mock_run.assert_called_once_with('git', 'credential', 'fill',
                                         stdin=b'url=%s' % url.encode('utf-8'))
        mock_get.assert_called_once_with(url)

    @mock.patch('sys.argv', ['argv0', '--track', 'branch'])
    @mock.patch('git_review.cmd.check_remote')
    @mock.patch('git_review.cmd.resolve_tracking')
    def test_command_line_no_track(self, resolve_tracking, check_remote):
        check_remote.side_effect = Exception()
        self.assertRaises(Exception, cmd._main)
        self.assertFalse(resolve_tracking.called)

    @mock.patch('sys.argv', ['argv0', '--track'])
    @mock.patch('git_review.cmd.check_remote')
    @mock.patch('git_review.cmd.resolve_tracking')
    def test_track(self, resolve_tracking, check_remote):
        check_remote.side_effect = Exception()
        self.assertRaises(Exception, cmd._main)
        self.assertTrue(resolve_tracking.called)


class DownloadFlagUnitTest(testtools.TestCase):

    def setUp(self):
        super(DownloadFlagUnitTest, self).setUp()
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument(
            '-d',
            action=cmd._DownloadFlag,
            const='download',
            dest='cid',
        )

    def test_store_id(self):
        args = self.parser.parse_args(['-d', '12345'])
        self.assertEqual('12345', args.cid)

    def test_parse_url(self):
        args = self.parser.parse_args(
            ['-d',
             'https://review.openstack.org/12345']
        )
        self.assertEqual('12345', args.cid)

    def test_parse_url_trailing_slash(self):
        args = self.parser.parse_args(
            ['-d',
             'https://review.openstack.org/12345/']
        )
        self.assertEqual('12345', args.cid)

    def test_parse_url_with_update(self):
        args = self.parser.parse_args(
            ['-d',
             'https://review.openstack.org/12345/2']
        )
        self.assertEqual('12345,2', args.cid)

    def test_parse_url_with_hash(self):
        args = self.parser.parse_args(
            ['-d',
             'https://review.openstack.org/#/c/12345']
        )
        self.assertEqual('12345', args.cid)

    def test_parse_url_with_hash_and_update(self):
        args = self.parser.parse_args(
            ['-d',
             'https://review.openstack.org/#/c/12345/1']
        )
        self.assertEqual('12345,1', args.cid)

    def test_parse_polygerrit_url(self):
        args = self.parser.parse_args(
            ['-d',
             'https://review.openstack.org/c/org/project/+/12345']
        )
        self.assertEqual('12345', args.cid)
