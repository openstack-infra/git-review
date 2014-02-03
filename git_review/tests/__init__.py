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
import stat
import sys

if sys.version < '3':
    import urllib
    urlopen = urllib.urlopen
else:
    import urllib.request
    urlopen = urllib.request.urlopen

import fixtures
import testtools
from testtools import content

from git_review.tests import utils


class GerritHelpers(object):

    def _dir(self, base, *args):
        """Creates directory name from base name and other parameters."""
        return os.path.join(getattr(self, base + '_dir'), *args)

    def init_dirs(self):
        self.primary_dir = os.path.abspath(os.path.curdir)
        self.gerrit_dir = self._dir('primary', '.gerrit')
        self.gsite_dir = self._dir('gerrit', 'golden_site')

    def ensure_gerrit_war(self):
        # check if gerrit.war file exists in .gerrit directory
        if not os.path.exists(self.gerrit_dir):
            os.mkdir(self.gerrit_dir)

        if not os.path.exists(self._dir('gerrit', 'gerrit.war')):
            resp = urlopen(
                'http://gerrit-releases.storage.googleapis.com/'
                'gerrit-2.6.1.war'
            )

            utils.write_to_file(self._dir('gerrit', 'gerrit.war'),
                                resp.read())

    def init_gerrit(self):
        """Run Gerrit from the war file and configure it."""
        if os.path.exists(self.gsite_dir):
            return

        # initialize Gerrit
        utils.run_cmd('java', '-jar', self._dir('gerrit', 'gerrit.war'),
                      'init', '-d', self.gsite_dir,
                      '--batch', '--no-auto-start')

        # create SSH public key
        key_file = self._dir('gsite', 'test_ssh_key')
        utils.run_cmd('ssh-keygen', '-t', 'rsa', '-b', '4096',
                                    '-f', key_file, '-N', '')
        with open(key_file + '.pub', 'rb') as pub_key_file:
            pub_key = pub_key_file.read()

        # create admin user in Gerrit database
        sql_query = """INSERT INTO ACCOUNTS (REGISTERED_ON) VALUES (NOW());
        INSERT INTO ACCOUNT_GROUP_MEMBERS (ACCOUNT_ID, GROUP_ID) \
            VALUES (0, 1);
        INSERT INTO ACCOUNT_EXTERNAL_IDS (ACCOUNT_ID, EXTERNAL_ID) \
            VALUES (0, 'username:test_user');
        INSERT INTO ACCOUNT_SSH_KEYS (SSH_PUBLIC_KEY, VALID) \
            VALUES ('%s', 'Y')""" % pub_key.decode()

        utils.run_cmd('java', '-jar',
                      self._dir('gsite', 'bin', 'gerrit.war'),
                      'gsql', '-d', self.gsite_dir, '-c', sql_query)

    def _run_gerrit_cli(self, command, *args):
        """SSH to gerrit Gerrit server and run command there."""
        return utils.run_cmd('ssh', '-p', str(self.gerrit_port),
                             'test_user@' + self.gerrit_host, 'gerrit',
                             command, *args)

    def _run_git_review(self, *args, **kwargs):
        """Run git-review utility from source."""
        git_review = utils.run_cmd('which', 'git-review')
        return utils.run_cmd(git_review, *args,
                             chdir=self.test_dir, **kwargs)


class BaseGitReviewTestCase(testtools.TestCase, GerritHelpers):
    """Base class for the git-review tests."""

    _test_counter = 0

    def setUp(self):
        """Configure testing environment.

        Prepare directory for the testing and clone test Git repository.
        Require Gerrit war file in the .gerrit directory to run Gerrit local.
        """
        super(BaseGitReviewTestCase, self).setUp()
        self.useFixture(fixtures.Timeout(2 * 60, True))
        BaseGitReviewTestCase._test_counter += 1

        self.init_dirs()
        ssh_addr, ssh_port, http_addr, http_port, self.site_dir = \
            self._pick_gerrit_port_and_dir()
        self.gerrit_host, self.gerrit_port = ssh_addr, ssh_port

        self.test_dir = self._dir('site', 'tmp', 'test_project')
        self.ssh_dir = self._dir('site', 'tmp', 'ssh')
        self.project_uri = 'ssh://test_user@%s:%s/test/test_project.git' % (
            ssh_addr, ssh_port)

        self._run_gerrit(ssh_addr, ssh_port, http_addr, http_port)
        self._configure_ssh(ssh_addr, ssh_port)

        # create Gerrit empty project
        self._run_gerrit_cli('create-project', '--empty-commit',
                             '--name', 'test/test_project')

        # prepare repository for the testing
        self._run_git('clone', self.project_uri)
        utils.write_to_file(self._dir('test', 'test_file.txt'),
                            'test file created'.encode())
        cfg = ('[gerrit]\n'
               'host=%s\n'
               'port=%s\n'
               'project=test/test_project.git' % (ssh_addr, ssh_port))
        utils.write_to_file(self._dir('test', '.gitreview'), cfg.encode())

        # push changes to the Gerrit
        self._run_git('add', '--all')
        self._run_git('commit', '-m', 'Test file and .gitreview added.')
        self._run_git('push', 'origin', 'master')
        shutil.rmtree(self.test_dir)

        # go to the just cloned test Git repository
        self._run_git('clone', self.project_uri)
        self._run_git('remote', 'add', 'gerrit', self.project_uri)
        self.addCleanup(shutil.rmtree, self.test_dir)

    def _run_git(self, command, *args):
        """Run git command using test git directory."""
        if command == 'clone':
            return utils.run_git(command, args[0], self._dir('test'))
        return utils.run_git('--git-dir=' + self._dir('test', '.git'),
                             '--work-tree=' + self._dir('test'),
                             command, *args)

    def _run_gerrit(self, ssh_addr, ssh_port, http_addr, http_port):
        # create a copy of site dir
        shutil.copytree(self.gsite_dir, self.site_dir)
        self.addCleanup(shutil.rmtree, self.site_dir)
        # write config
        with open(self._dir('site', 'etc', 'gerrit.config'), 'w') as _conf:
            new_conf = utils.get_gerrit_conf(
                ssh_addr, ssh_port, http_addr, http_port)
            _conf.write(new_conf)

        # If test fails, attach Gerrit logs to the result
        @self.addOnException
        def add_logs(exc_info):
            for name in ['error_log', 'sshd_log', 'httpd_log']:
                content.attach_file(self, self._dir('site', 'logs', name))

        # start Gerrit
        gerrit_sh = self._dir('site', 'bin', 'gerrit.sh')
        utils.run_cmd(gerrit_sh, 'start')
        self.addCleanup(utils.run_cmd, gerrit_sh, 'stop')

    def _simple_change(self, change_text, commit_message,
                       file_=None):
        """Helper method to create small changes and commit them."""
        if file_ is None:
            file_ = self._dir('test', 'test_file.txt')
        utils.write_to_file(file_, change_text.encode())
        self._run_git('add', file_)
        self._run_git('commit', '-m', commit_message)

    def _configure_ssh(self, ssh_addr, ssh_port):
        """Setup ssh and scp to run with special options."""

        os.mkdir(self.ssh_dir)

        ssh_key = utils.run_cmd('ssh-keyscan', '-p', str(ssh_port), ssh_addr)
        utils.write_to_file(self._dir('ssh', 'known_hosts'), ssh_key.encode())
        self.addCleanup(os.remove, self._dir('ssh', 'known_hosts'))

        # Attach known_hosts to test results if anything fails
        @self.addOnException
        def add_known_hosts(exc_info):
            known_hosts = self._dir('ssh', 'known_hosts')
            if os.path.exists(known_hosts):
                content.attach_file(self, known_hosts)
            else:
                self.addDetail('known_hosts',
                               content.text_content('Not found'))

        for cmd in ('ssh', 'scp'):
            cmd_file = self._dir('ssh', cmd)
            s = '#!/bin/sh\n' \
                '/usr/bin/%s -i %s -o UserKnownHostsFile=%s $@' % \
                (cmd,
                 self._dir('gsite', 'test_ssh_key'),
                 self._dir('ssh', 'known_hosts'))
            utils.write_to_file(cmd_file, s.encode())
            os.chmod(cmd_file, os.stat(cmd_file).st_mode | stat.S_IEXEC)

        os.environ['PATH'] = self.ssh_dir + os.pathsep + os.environ['PATH']
        os.environ['GIT_SSH'] = self._dir('ssh', 'ssh')

    def _pick_gerrit_port_and_dir(self):
        pid = os.getpid()
        host = '127.%s.%s.%s' % (self._test_counter, pid >> 8, pid & 255)
        return host, 29418, host, 8080, self._dir('gerrit', 'site-' + host)
