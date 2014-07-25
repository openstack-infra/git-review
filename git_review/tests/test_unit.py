# -*- coding: utf8 -*-

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

# Use of io.StringIO in python =< 2.7 requires all strings handled to be
# unicode. See if StringIO.StringIO is available first
try:
    import StringIO as io
except ImportError:
    import io
import textwrap

import mock
import testtools

import git_review


class GitReviewConsole(testtools.TestCase):
    """Class for testing the console output of git-review."""

    reviews = [
        {
            'number': '1010101',
            'branch': 'master',
            'subject': 'A simple short subject'
        }, {
            'number': '9877',
            'branch': 'stable/codeword',
            'subject': 'A longer and slightly more wordy subject'
        }, {
            'number': '12345',
            'branch': 'master',
            'subject': 'A ridiculously long subject that can exceed the '
                       'normal console width, just need to ensure the '
                       'max width is short enough'
        }]

    @mock.patch('git_review.cmd.query_reviews')
    @mock.patch('git_review.cmd.get_remote_url', mock.MagicMock)
    @mock.patch('git_review.cmd._has_color', False)
    def test_list_reviews_no_blanks(self, mock_query):

        mock_query.return_value = self.reviews
        with mock.patch('sys.stdout', new_callable=io.StringIO) as output:
            git_review.cmd.list_reviews(None)
            console_output = output.getvalue().split('\n')

        wrapper = textwrap.TextWrapper(replace_whitespace=False,
                                       drop_whitespace=False)
        for text in console_output:
            for line in wrapper.wrap(text):
                self.assertEqual(line.isspace(), False,
                                 "Extra blank lines appearing between reviews"
                                 "in console output")
