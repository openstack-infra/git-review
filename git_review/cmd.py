#!/usr/bin/env python
from __future__ import print_function

COPYRIGHT = """\
Copyright (C) 2011-2012 OpenStack LLC.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
implied.

See the License for the specific language governing permissions and
limitations under the License."""

import argparse
import datetime
import json
import os
import re
import shlex
import subprocess
import sys
import textwrap

import pkg_resources
import requests

if sys.version < '3':
    import ConfigParser
    import urllib
    import urlparse
    urlencode = urllib.urlencode
    urljoin = urlparse.urljoin
    urlparse = urlparse.urlparse
    do_input = raw_input
else:
    import configparser as ConfigParser

    import urllib.parse
    import urllib.request
    urlencode = urllib.parse.urlencode
    urljoin = urllib.parse.urljoin
    urlparse = urllib.parse.urlparse
    do_input = input

VERBOSE = False
UPDATE = False
LOCAL_MODE = 'GITREVIEW_LOCAL_MODE' in os.environ
CONFIGDIR = os.path.expanduser("~/.config/git-review")
GLOBAL_CONFIG = "/etc/git-review/git-review.conf"
USER_CONFIG = os.path.join(CONFIGDIR, "git-review.conf")
DEFAULTS = dict(scheme='ssh', hostname=False, port=None, project=False,
                branch='master', remote="gerrit", rebase="1")

_branch_name = None
_has_color = None
_use_color = None
_orig_head = None
_rewrites = None


class colors:
    yellow = '\033[33m'
    green = '\033[92m'
    reset = '\033[0m'


class GitReviewException(Exception):
    pass


class CommandFailed(GitReviewException):

    def __init__(self, *args):
        Exception.__init__(self, *args)
        (self.rc, self.output, self.argv, self.envp) = args
        self.quickmsg = dict([
            ("argv", " ".join(self.argv)),
            ("rc", self.rc),
            ("output", self.output)])

    def __str__(self):
        return self.__doc__ + """
The following command failed with exit code %(rc)d
    "%(argv)s"
-----------------------
%(output)s
-----------------------""" % self.quickmsg


class ChangeSetException(GitReviewException):

    def __init__(self, e):
        GitReviewException.__init__(self)
        self.e = str(e)

    def __str__(self):
        return self.__doc__ % self.e


def printwrap(unwrapped):
    print('\n'.join(textwrap.wrap(unwrapped)))


def parse_review_number(review):
    parts = review.split(',')
    if len(parts) < 2:
        parts.append(None)
    return parts


def build_review_number(review, patchset):
    if patchset is not None:
        return '%s,%s' % (review, patchset)
    return review


def run_command_status(*argv, **kwargs):
    if VERBOSE:
        print(datetime.datetime.now(), "Running:", " ".join(argv))
    if len(argv) == 1:
        # for python2 compatibility with shlex
        if sys.version_info < (3,) and isinstance(argv[0], unicode):
            argv = shlex.split(argv[0].encode('utf-8'))
        else:
            argv = shlex.split(str(argv[0]))
    stdin = kwargs.pop('stdin', None)
    newenv = os.environ.copy()
    newenv.update(kwargs)
    p = subprocess.Popen(argv,
                         stdin=subprocess.PIPE if stdin else None,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT,
                         env=newenv)
    (out, nothing) = p.communicate(stdin)
    out = out.decode('utf-8', 'replace')
    return (p.returncode, out.strip())


def run_command(*argv, **kwargs):
    (rc, output) = run_command_status(*argv, **kwargs)
    return output


def run_command_exc(klazz, *argv, **env):
    """Run command *argv, on failure raise klazz

    klazz should be derived from CommandFailed
    """
    (rc, output) = run_command_status(*argv, **env)
    if rc != 0:
        raise klazz(rc, output, argv, env)
    return output


def git_credentials(klazz, url):
    """Get credentials using git credential."""
    cmd = 'git', 'credential', 'fill'
    stdin = 'url=%s' % url
    out = run_command_exc(klazz, *cmd, stdin=stdin)
    data = dict(l.split('=', 1) for l in out.splitlines())
    return data['username'], data['password']


def http_code_2_return_code(code):
    """Tranform http status code to system return code."""
    return (code - 301) % 255 + 1


def run_http_exc(klazz, url, **env):
    """Run http GET request url, on failure raise klazz

    klazz should be derived from CommandFailed
    """
    if url.startswith("https://") and "verify" not in env:
        if "GIT_SSL_NO_VERIFY" in os.environ:
            env["verify"] = False
        else:
            verify = git_config_get_value("http", "sslVerify", as_bool=True)
            env["verify"] = verify != 'false'

    try:
        res = requests.get(url, **env)
        if res.status_code == 401:
            env['auth'] = git_credentials(klazz, url)
            res = requests.get(url, **env)
    except klazz:
        raise
    except Exception as err:
        raise klazz(255, str(err), ('GET', url), env)
    if not 200 <= res.status_code < 300:
        raise klazz(http_code_2_return_code(res.status_code),
                    res.text, ('GET', url), env)
    return res


def get_version():
    requirement = pkg_resources.Requirement.parse('git-review')
    provider = pkg_resources.get_provider(requirement)
    return provider.version


def git_directories():
    """Determine (absolute git work directory path, .git subdirectory path)."""
    cmd = ("git", "rev-parse", "--show-toplevel", "--git-dir")
    out = run_command_exc(GitDirectoriesException, *cmd)
    try:
        return out.splitlines()
    except ValueError:
        raise GitDirectoriesException(0, out, cmd, {})


class GitDirectoriesException(CommandFailed):
    "Cannot determine where .git directory is."
    EXIT_CODE = 70


class CustomScriptException(CommandFailed):
    """Custom script execution failed."""
    EXIT_CODE = 71


def run_custom_script(action):
    """Get status and output of .git/hooks/$action-review or/and
    ~/.config/hooks/$action-review if existing.
    """
    returns = []
    script_file = "%s-review" % (action)
    (top_dir, git_dir) = git_directories()
    paths = [os.path.join(CONFIGDIR, "hooks", script_file),
             os.path.join(git_dir, "hooks", script_file)]
    for fpath in paths:
        if os.path.isfile(fpath) and os.access(fpath, os.X_OK):
            status, output = run_command_status(fpath)
            returns.append((status, output, fpath))

    for (status, output, path) in returns:
        if status is not None and status != 0:
            raise CustomScriptException(status, output, [path], {})
        elif output and VERBOSE:
            print("script %s output is:" % (path))
            print(output)


def git_config_get_value(section, option, default=None, as_bool=False):
    """Get config value for section/option."""
    cmd = ["git", "config", "--get", "%s.%s" % (section, option)]
    if as_bool:
        cmd.insert(2, "--bool")
    if LOCAL_MODE:
        __, git_dir = git_directories()
        cmd[2:2] = ['-f', os.path.join(git_dir, 'config')]
    try:
        return run_command_exc(GitConfigException, *cmd).strip()
    except GitConfigException as exc:
        if exc.rc == 1:
            return default
        raise


class Config(object):
    """Expose as dictionary configuration options."""

    def __init__(self, config_file=None):
        self.config = DEFAULTS.copy()
        filenames = [] if LOCAL_MODE else [GLOBAL_CONFIG, USER_CONFIG]
        if config_file:
            filenames.append(config_file)
        for filename in filenames:
            if os.path.exists(filename):
                if filename != config_file:
                    msg = ("Using global/system git-review config files (%s) "
                           "is deprecated")
                    print(msg % filename)
                self.config.update(load_config_file(filename))

    def __getitem__(self, key):
        value = git_config_get_value('gitreview', key)
        if value is None:
            value = self.config[key]
        return value


class GitConfigException(CommandFailed):
    """Git config value retrieval failed."""
    EXIT_CODE = 128


class CannotInstallHook(CommandFailed):
    "Problems encountered installing commit-msg hook"
    EXIT_CODE = 2


def set_hooks_commit_msg(remote, target_file):
    """Install the commit message hook if needed."""

    # Create the hooks directory if it's not there already
    hooks_dir = os.path.dirname(target_file)
    if not os.path.isdir(hooks_dir):
        os.mkdir(hooks_dir)

    if not os.path.exists(target_file) or UPDATE:
        remote_url = get_remote_url(remote)
        if (remote_url.startswith('http://') or
                remote_url.startswith('https://')):
            hook_url = urljoin(remote_url, '/tools/hooks/commit-msg')
            if VERBOSE:
                print("Fetching commit hook from: %s" % hook_url)
            res = run_http_exc(CannotInstallHook, hook_url, stream=True)
            with open(target_file, 'wb') as f:
                for x in res.iter_content(1024):
                    f.write(x)
        else:
            (hostname, username, port, project_name) = \
                parse_gerrit_ssh_params_from_git_url(remote_url)
            if username is None:
                userhost = hostname
            else:
                userhost = "%s@%s" % (username, hostname)
            # OS independent target file
            scp_target_file = target_file.replace(os.sep, "/")
            cmd = ["scp", userhost + ":hooks/commit-msg", scp_target_file]
            if port is not None:
                cmd.insert(1, "-P%s" % port)

            if VERBOSE:
                hook_url = 'scp://%s%s/hooks/commit-msg' \
                    % (userhost, (":%s" % port) if port else "")
                print("Fetching commit hook from: %s" % hook_url)
            run_command_exc(CannotInstallHook, *cmd)

    if not os.access(target_file, os.X_OK):
        os.chmod(target_file, os.path.stat.S_IREAD | os.path.stat.S_IEXEC)


def test_remote_url(remote_url):
    """Tests that a possible gerrit remote url works."""
    status, __ = run_command_status("git", "push", "--dry-run", remote_url,
                                    "--all")
    if status != 128:
        if VERBOSE:
            print("%s worked." % remote_url)
        return True
    else:
        if VERBOSE:
            print("%s did not work." % remote_url)
        return False


def make_remote_url(scheme, username, hostname, port, project):
    """Builds a gerrit remote URL."""
    if port is None and scheme == 'ssh':
        port = 29418
    hostport = '%s:%s' % (hostname, port) if port else hostname
    if username is None:
        return "%s://%s/%s" % (scheme, hostport, project)
    else:
        return "%s://%s@%s/%s" % (scheme, username, hostport, project)


def add_remote(scheme, hostname, port, project, remote):
    """Adds a gerrit remote."""
    asked_for_username = False

    username = git_config_get_value("gitreview", "username")
    if not username:
        username = os.getenv("USERNAME")
    if not username:
        username = os.getenv("USER")

    remote_url = make_remote_url(scheme, username, hostname, port, project)
    if VERBOSE:
        print("No remote set, testing %s" % remote_url)
    if not test_remote_url(remote_url):
        print("Could not connect to gerrit.")
        username = do_input("Enter your gerrit username: ")
        remote_url = make_remote_url(scheme, username, hostname, port, project)
        print("Trying again with %s" % remote_url)
        if not test_remote_url(remote_url):
            raise GitReviewException("Could not connect to gerrit at "
                                     "%s" % remote_url)
        asked_for_username = True

    print("Creating a git remote called \"%s\" that maps to:" % remote)
    print("\t%s" % remote_url)
    cmd = "git remote add -f %s %s" % (remote, remote_url)
    (status, remote_output) = run_command_status(cmd)

    if status != 0:
        raise CommandFailed(status, remote_output, cmd, {})

    if asked_for_username:
        print()
        printwrap("This repository is now set up for use with git-review. "
                  "You can set the default username for future repositories "
                  "with:")
        print('  git config --global --add gitreview.username "%s"' % username)
        print()


def populate_rewrites():
    """Populate the global _rewrites map based on the output of "git-config".
    """

    cmd = ['git', 'config', '--list']
    out = run_command_exc(CommandFailed, *cmd).strip()

    global _rewrites
    _rewrites = {}

    for entry in out.splitlines():
        key, _, value = entry.partition('=')
        key = key.lower()

        if key.startswith('url.') and key.endswith('.insteadof'):
            rewrite = key[4:-10]
            if rewrite:
                _rewrites[value] = rewrite


def alias_url(url):
    """Expand a remote URL. Use the global map _rewrites to replace the
    longest match with its equivalent.
    """

    if _rewrites is None:
        populate_rewrites()

    longest = None
    for alias in _rewrites:
        if (url.startswith(alias)
                and (longest is None or len(longest) < len(alias))):
            longest = alias

    if longest:
        url = url.replace(longest, _rewrites[longest])
    return url


def get_remote_url(remote):
    """Retrieve the remote URL. Read the configuration to expand the URL of a
    remote repository taking into account any "url.<base>.insteadOf" config
    setting.

    TODO: Replace current code with "git ls-remote --get-url" when the
    continuous builders will support it. It requires the use of Git v1.7.5
    or above. Beware that option "--get-url" of "git-ls-remote" is
    supported since v1.7.5 (see https://github.com/git/git/commit/45781ad) but
    was not properly documented until v1.7.12.2.
    """

    url = git_config_get_value('remote.%s' % remote, 'url', '')
    push_url = git_config_get_value('remote.%s' % remote, 'pushurl', url)
    push_url = alias_url(push_url)
    if VERBOSE:
        print("Found origin Push URL:", push_url)
    return push_url


def parse_gerrit_ssh_params_from_git_url(git_url):
    """Parse a given Git "URL" into Gerrit parameters. Git "URLs" are either
    real URLs or SCP-style addresses.
    """

    # The exact code for this in Git itself is a bit obtuse, so just do
    # something sensible and pythonic here instead of copying the exact
    # minutiae from Git.

    # Handle real(ish) URLs
    if "://" in git_url:
        parsed_url = urlparse(git_url)
        path = parsed_url.path

        hostname = parsed_url.netloc
        username = None
        port = parsed_url.port

        # Workaround bug in urlparse on OSX
        if parsed_url.scheme == "ssh" and parsed_url.path[:2] == "//":
            hostname = parsed_url.path[2:].split("/")[0]

        if "@" in hostname:
            (username, hostname) = hostname.split("@")
        if ":" in hostname:
            (hostname, port) = hostname.split(":")

        if port is not None:
            port = str(port)

    # Handle SCP-style addresses
    else:
        username = None
        port = None
        (hostname, path) = git_url.split(":", 1)
        if "@" in hostname:
            (username, hostname) = hostname.split("@", 1)

    # Strip leading slash and trailing .git from the path to form the project
    # name.
    project_name = re.sub(r"^/|(\.git$)", "", path)

    return (hostname, username, port, project_name)


def query_reviews(remote_url, change=None, current_patch_set=True,
                  exception=CommandFailed, parse_exc=Exception):
    if remote_url.startswith('http://') or remote_url.startswith('https://'):
        query = query_reviews_over_http
    else:
        query = query_reviews_over_ssh
    return query(remote_url,
                 change=change,
                 current_patch_set=current_patch_set,
                 exception=exception,
                 parse_exc=parse_exc)


def query_reviews_over_http(remote_url, change=None, current_patch_set=True,
                            exception=CommandFailed, parse_exc=Exception):
    url = urljoin(remote_url, '/changes/')
    if change:
        if current_patch_set:
            url += '?q=%s&o=CURRENT_REVISION' % change
        else:
            url += '?q=%s&o=ALL_REVISIONS' % change
    else:
        project_name = re.sub(r"^/|(\.git$)", "", urlparse(remote_url).path)
        params = urlencode({'q': 'project:%s status:open' % project_name})
        url += '?' + params

    if VERBOSE:
        print("Query gerrit %s" % url)
    request = run_http_exc(exception, url)
    if VERBOSE:
        print(request.text)
    reviews = json.loads(request.text[4:])

    # Reformat output to match ssh output
    try:
        for review in reviews:
            review["number"] = str(review.pop("_number"))
            if "revisions" not in review:
                continue
            patchsets = {}
            for key, revision in review["revisions"].items():
                fetch_value = list(revision["fetch"].values())[0]
                patchset = {"number": str(revision["_number"]),
                            "ref": fetch_value["ref"]}
                patchsets[key] = patchset
            review["patchSets"] = patchsets.values()
            review["currentPatchSet"] = patchsets[review["current_revision"]]
    except Exception as err:
        raise parse_exc(err)

    return reviews


def query_reviews_over_ssh(remote_url, change=None, current_patch_set=True,
                           exception=CommandFailed, parse_exc=Exception):
    (hostname, username, port, project_name) = \
        parse_gerrit_ssh_params_from_git_url(remote_url)

    if change:
        if current_patch_set:
            query = "--current-patch-set change:%s" % change
        else:
            query = "--patch-sets change:%s" % change
    else:
        query = "project:%s status:open" % project_name

    port_data = "p%s" % port if port is not None else ""
    if username is None:
        userhost = hostname
    else:
        userhost = "%s@%s" % (username, hostname)

    if VERBOSE:
        print("Query gerrit %s %s" % (remote_url, query))
    output = run_command_exc(
        exception,
        "ssh", "-x" + port_data, userhost,
        "gerrit", "query",
        "--format=JSON %s" % query)
    if VERBOSE:
        print(output)

    changes = []
    try:
        for line in output.split("\n"):
            if line[0] == "{":
                try:
                    data = json.loads(line)
                    if "type" not in data:
                        changes.append(data)
                except Exception:
                    if VERBOSE:
                        print(output)
    except Exception as err:
        raise parse_exc(err)
    return changes


def set_color_output(color="auto"):
    global _use_color
    if check_color_support():
        if color == "auto":
            check_use_color_output()
        else:
            _use_color = color == "always"


def check_use_color_output():
    global _use_color
    if _use_color is None:
        if check_color_support():
            # we can support color, now check if we should use it
            stdout = "true" if sys.stdout.isatty() else "false"
            test_command = "git config --get-colorbool color.review " + stdout
            color = run_command(test_command)
            _use_color = color == "true"
        else:
            _use_color = False
    return _use_color


def check_color_support():
    global _has_color
    if _has_color is None:
        test_command = "git log --color=never --oneline HEAD^1..HEAD"
        (status, output) = run_command_status(test_command)
        if status == 0:
            _has_color = True
        else:
            _has_color = False
    return _has_color


def load_config_file(config_file):
    """Load configuration options from a file."""
    configParser = ConfigParser.ConfigParser()
    configParser.read(config_file)
    options = {
        'scheme': 'scheme',
        'hostname': 'host',
        'port': 'port',
        'project': 'project',
        'branch': 'defaultbranch',
        'remote': 'defaultremote',
        'rebase': 'defaultrebase',
    }
    config = {}
    for config_key, option_name in options.items():
        if configParser.has_option('gerrit', option_name):
            config[config_key] = configParser.get('gerrit', option_name)
    return config


def update_remote(remote):
    cmd = "git remote update %s" % remote
    (status, output) = run_command_status(cmd)
    if VERBOSE:
        print(output)
    if status != 0:
        print("Problem running '%s'" % cmd)
        if not VERBOSE:
            print(output)
        return False
    return True


def check_remote(branch, remote, scheme, hostname, port, project):
    """Check that a Gerrit Git remote repo exists, if not, set one."""

    has_color = check_color_support()
    if has_color:
        color_never = "--color=never"
    else:
        color_never = ""

    if remote in run_command("git remote").split("\n"):

        remotes = run_command("git branch -a %s" % color_never).split("\n")
        for current_remote in remotes:
            if (current_remote.strip() == "remotes/%s/%s" % (remote, branch)
                    and not UPDATE):
                return
        # We have the remote, but aren't set up to fetch. Fix it
        if VERBOSE:
            print("Setting up gerrit branch tracking for better rebasing")
        update_remote(remote)
        return

    if hostname is False or project is False:
        # This means there was no .gitreview file
        printwrap("No '.gitreview' file found in this repository. We don't "
                  "know where your gerrit is. Please manually create a remote "
                  "named \"%s\" and try again." % remote)
        sys.exit(1)

    # Gerrit remote not present, try to add it
    try:
        add_remote(scheme, hostname, port, project, remote)
    except Exception:
        print(sys.exc_info()[2])
        printwrap("We don't know where your gerrit is. Please manually create "
                  "a remote named \"%s\" and try again." % remote)
        raise


def rebase_changes(branch, remote, interactive=True):

    global _orig_head

    remote_branch = "remotes/%s/%s" % (remote, branch)

    if not update_remote(remote):
        return False

    # since the value of ORIG_HEAD may not be set by rebase as expected
    # for use in undo_rebase, make sure to save it explicitly
    cmd = "git rev-parse HEAD"
    (status, output) = run_command_status(cmd)
    if status != 0:
        print("Errors running %s" % cmd)
        if interactive:
            print(output)
        return False
    _orig_head = output

    cmd = "git show-ref --quiet --verify refs/%s" % remote_branch
    (status, output) = run_command_status(cmd)
    if status != 0:
        printwrap("The branch '%s' does not exist on the given remote '%s'. "
                  "If these changes are intended to start a new branch, "
                  "re-run with the '-R' option enabled." % (branch, remote))
        sys.exit(1)

    if interactive:
        cmd = "git rebase -p -i %s" % remote_branch
    else:
        cmd = "git rebase -p %s" % remote_branch

    (status, output) = run_command_status(cmd, GIT_EDITOR='true')
    if status != 0:
        print("Errors running %s" % cmd)
        if interactive:
            print(output)
        return False
    return True


def undo_rebase():
    global _orig_head
    if not _orig_head:
        return True

    cmd = "git reset --hard %s" % _orig_head
    (status, output) = run_command_status(cmd)
    if status != 0:
        print("Errors running %s" % cmd)
        print(output)
        return False
    return True


def get_branch_name(target_branch):
    global _branch_name
    if _branch_name is not None:
        return _branch_name
    _branch_name = None
    cmd = "git branch"
    has_color = check_color_support()
    if has_color:
        cmd += " --color=never"
    for branch in run_command(cmd, LANG='C').split("\n"):
        if branch.startswith('*'):
            _branch_name = branch.split()[1].strip()
            break
    if _branch_name == "(no" or _branch_name == "(detached":
        _branch_name = target_branch
    return _branch_name


def assert_one_change(remote, branch, yes, have_hook):
    if check_use_color_output():
        use_color = "--color=always"
    else:
        use_color = "--color=never"
    cmd = ("git log %s --decorate --oneline HEAD --not --remotes=%s" % (
           use_color, remote))
    (status, output) = run_command_status(cmd)
    if status != 0:
        print("Had trouble running %s" % cmd)
        print(output)
        sys.exit(1)
    filtered = filter(None, output.split("\n"))
    output_lines = sum(1 for s in filtered)
    if output_lines == 1 and not have_hook:
        printwrap("Your change was committed before the commit hook was "
                  "installed. Amending the commit to add a gerrit change id.")
        run_command("git commit --amend", GIT_EDITOR='true')
    elif output_lines == 0:
        printwrap("No changes between HEAD and %s/%s. Submitting for review "
                  "would be pointless." % (remote, branch))
        sys.exit(1)
    elif output_lines > 1:
        if not yes:
            printwrap("You are about to submit multiple commits. This is "
                      "expected if you are submitting a commit that is "
                      "dependent on one or more in-review commits. Otherwise "
                      "you should consider squashing your changes into one "
                      "commit before submitting.")
            print("\nThe outstanding commits are:\n\n%s\n\n"
                  "Do you really want to submit the above commits?" % output)
            yes_no = do_input("Type 'yes' to confirm, other to cancel: ")
            if yes_no.lower().strip() != "yes":
                print("Aborting.")
                sys.exit(1)


def use_topic(why, topic):
    """Inform the user about why a particular topic has been selected."""
    if VERBOSE:
        print(why % ('"%s"' % topic,))
    return topic


def get_topic(target_branch):

    branch_name = get_branch_name(target_branch)

    branch_parts = branch_name.split("/")
    if len(branch_parts) >= 3 and branch_parts[0] == "review":
        return use_topic("Using change number %s "
                         "for the topic of the change submitted",
                         "/".join(branch_parts[2:]))

    log_output = run_command("git log HEAD^1..HEAD")
    bug_re = r'''(?x)                # verbose regexp
                 \b([Bb]ug|[Ll][Pp]) # bug or lp
                 [ \t\f\v]*          # don't want to match newline
                 [:]?                # separator if needed
                 [ \t\f\v]*          # don't want to match newline
                 [#]?                # if needed
                 [ \t\f\v]*          # don't want to match newline
                 (\d+)               # bug number'''

    match = re.search(bug_re, log_output)
    if match is not None:
        return use_topic("Using bug number %s "
                         "for the topic of the change submitted",
                         "bug/%s" % match.group(2))

    bp_re = r'''(?x)                         # verbose regexp
                \b([Bb]lue[Pp]rint|[Bb][Pp]) # a blueprint or bp
                [ \t\f\v]*                   # don't want to match newline
                [#:]?                        # separator if needed
                [ \t\f\v]*                   # don't want to match newline
                ([0-9a-zA-Z-_]+)             # any identifier or number'''
    match = re.search(bp_re, log_output)
    if match is not None:
        return use_topic("Using blueprint number %s "
                         "for the topic of the change submitted",
                         "bp/%s" % match.group(2))

    return use_topic("Using local branch name %s "
                     "for the topic of the change submitted",
                     branch_name)


class CannotQueryOpenChangesets(CommandFailed):
    "Cannot fetch review information from gerrit"
    EXIT_CODE = 32


class CannotParseOpenChangesets(ChangeSetException):
    "Cannot parse JSON review information from gerrit"
    EXIT_CODE = 33


def list_reviews(remote):
    remote_url = get_remote_url(remote)
    reviews = query_reviews(remote_url,
                            exception=CannotQueryOpenChangesets,
                            parse_exc=CannotParseOpenChangesets)

    if not reviews:
        print("No pending reviews")
        return

    REVIEW_FIELDS = ('number', 'branch', 'subject')
    FIELDS = range(len(REVIEW_FIELDS))
    if check_use_color_output():
        review_field_color = (colors.yellow, colors.green, "")
        color_reset = colors.reset
    else:
        review_field_color = ("", "", "")
        color_reset = ""
    review_field_format = ["%*s", "%*s", "%*s"]
    review_field_justify = [+1, +1, -1]  # +1 is justify to right

    review_list = [[r[f] for f in REVIEW_FIELDS] for r in reviews]
    review_field_width = dict()
    # assume last field is longest and may exceed the console width in which
    # case using the maximum value will result in extra blank lines appearing
    # after each entry even when only one field exceeds the console width
    for i in FIELDS[:-1]:
        review_field_width[i] = max(len(r[i]) for r in review_list)
    review_field_width[len(FIELDS) - 1] = 1

    review_field_format = "  ".join([
        review_field_color[i] +
        review_field_format[i] +
        color_reset
        for i in FIELDS])

    review_field_width = [
        review_field_width[i] * review_field_justify[i]
        for i in FIELDS]
    for review_value in review_list:
        # At this point we have review_field_format
        # like "%*s %*s %*s" and we need to supply
        # (width1, value1, width2, value2, ...) tuple to print
        # It's easy to zip() widths with actual values,
        # but we need to flatten the resulting
        #  ((width1, value1), (width2, value2), ...) map.
        formatted_fields = []
        for (width, value) in zip(review_field_width, review_value):
            formatted_fields.extend([width, value.encode('utf-8')])
        print(review_field_format % tuple(formatted_fields))
    print("Found %d items for review" % len(reviews))

    return 0


class CannotQueryPatchSet(CommandFailed):
    "Cannot query patchset information"
    EXIT_CODE = 34


class ReviewInformationNotFound(ChangeSetException):
    "Could not fetch review information for change %s"
    EXIT_CODE = 35


class ReviewNotFound(ChangeSetException):
    "Gerrit review %s not found"
    EXIT_CODE = 36


class PatchSetGitFetchFailed(CommandFailed):
    """Cannot fetch patchset contents

Does specified change number belong to this project?
"""
    EXIT_CODE = 37


class PatchSetNotFound(ChangeSetException):
    "Review patchset %s not found"
    EXIT_CODE = 38


class CheckoutNewBranchFailed(CommandFailed):
    "Cannot checkout to new branch"
    EXIT_CODE = 64


class CheckoutExistingBranchFailed(CommandFailed):
    "Cannot checkout existing branch"
    EXIT_CODE = 65


class ResetHardFailed(CommandFailed):
    "Failed to hard reset downloaded branch"
    EXIT_CODE = 66


def fetch_review(review, masterbranch, remote):
    remote_url = get_remote_url(remote)

    review_arg = review
    review, patchset_number = parse_review_number(review)
    current_patch_set = patchset_number is None

    review_infos = query_reviews(remote_url,
                                 change=review,
                                 current_patch_set=current_patch_set,
                                 exception=CannotQueryPatchSet,
                                 parse_exc=ReviewInformationNotFound)

    if not len(review_infos):
        raise ReviewInformationNotFound(review)
    review_info = review_infos[0]

    try:
        if patchset_number is None:
            refspec = review_info['currentPatchSet']['ref']
        else:
            refspec = [ps for ps in review_info['patchSets']
                       if ps['number'] == patchset_number][0]['ref']
    except IndexError:
        raise PatchSetNotFound(review_arg)
    except KeyError:
        raise ReviewNotFound(review)

    try:
        topic = review_info['topic']
        if topic == masterbranch:
            topic = review
    except KeyError:
        topic = review
    try:
        author = re.sub('\W+', '_', review_info['owner']['name']).lower()
    except KeyError:
        author = 'unknown'

    if patchset_number is None:
        branch_name = "review/%s/%s" % (author, topic)
    else:
        branch_name = "review/%s/%s-patch%s" % (author, topic, patchset_number)

    print("Downloading %s from gerrit" % refspec)
    run_command_exc(PatchSetGitFetchFailed,
                    "git", "fetch", remote, refspec)
    return branch_name


def checkout_review(branch_name):
    """Checkout a newly fetched (FETCH_HEAD) change
       into a branch
    """

    try:
        run_command_exc(CheckoutNewBranchFailed,
                        "git", "checkout", "-b",
                        branch_name, "FETCH_HEAD")

    except CheckoutNewBranchFailed as e:
        if re.search("already exists\.?", e.output):
            print("Branch already exists - reusing")
            run_command_exc(CheckoutExistingBranchFailed,
                            "git", "checkout", branch_name)
            run_command_exc(ResetHardFailed,
                            "git", "reset", "--hard", "FETCH_HEAD")
        else:
            raise

    print("Switched to branch \"%s\"" % branch_name)


class PatchSetGitCherrypickFailed(CommandFailed):
    "There was a problem applying changeset contents to the current branch."
    EXIT_CODE = 69


def cherrypick_review(option=None):
    cmd = ["git", "cherry-pick"]
    if option:
        cmd.append(option)
    cmd.append("FETCH_HEAD")
    print(run_command_exc(PatchSetGitCherrypickFailed, *cmd))


class CheckoutBackExistingBranchFailed(CommandFailed):
    "Cannot switch back to existing branch"
    EXIT_CODE = 67


class DeleteBranchFailed(CommandFailed):
    "Failed to delete branch"
    EXIT_CODE = 68


class InvalidPatchsetsToCompare(GitReviewException):
    def __init__(self, patchsetA, patchsetB):
        Exception.__init__(
            self,
            "Invalid patchsets for comparison specified (old=%s,new=%s)" % (
                patchsetA,
                patchsetB))
    EXIT_CODE = 39


def compare_review(review_spec, branch, remote, rebase=False):
    new_ps = None    # none means latest

    if '-' in review_spec:
        review_spec, new_ps = review_spec.split('-')
    review, old_ps = parse_review_number(review_spec)

    if old_ps is None or old_ps == new_ps:
        raise InvalidPatchsetsToCompare(old_ps, new_ps)

    old_review = build_review_number(review, old_ps)
    new_review = build_review_number(review, new_ps)

    old_branch = fetch_review(old_review, branch, remote)
    checkout_review(old_branch)

    if rebase:
        print('Rebasing %s' % old_branch)
        rebase = rebase_changes(branch, remote, False)
        if not rebase:
            print('Skipping rebase because of conflicts')
            run_command_exc(CommandFailed, 'git', 'rebase', '--abort')

    new_branch = fetch_review(new_review, branch, remote)
    checkout_review(new_branch)

    if rebase:
        print('Rebasing also %s' % new_branch)
        if not rebase_changes(branch, remote, False):
            print("Rebasing of the new branch failed, "
                  "diff can be messed up (use -R to not rebase at all)!")
            run_command_exc(CommandFailed, 'git', 'rebase', '--abort')

    subprocess.check_call(['git', 'diff', old_branch])


def finish_branch(target_branch):
    local_branch = get_branch_name(target_branch)
    if VERBOSE:
        print("Switching back to '%s' and deleting '%s'" % (target_branch,
                                                            local_branch))
    run_command_exc(CheckoutBackExistingBranchFailed,
                    "git", "checkout", target_branch)
    print("Switched to branch '%s'" % target_branch)

    run_command_exc(DeleteBranchFailed,
                    "git", "branch", "-D", local_branch)
    print("Deleted branch '%s'" % local_branch)


def convert_bool(one_or_zero):
    "Return a bool on a one or zero string."
    return str(one_or_zero) in ["1", "true", "True"]


def _main():
    usage = "git review [OPTIONS] ... [BRANCH]"

    class DownloadFlag(argparse.Action):
        """Additional option parsing: store value in 'dest', but
           at the same time set one of the flag options to True
        """
        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, values)
            setattr(namespace, self.const, True)

    parser = argparse.ArgumentParser(usage=usage, description=COPYRIGHT)

    topic_arg_group = parser.add_mutually_exclusive_group()
    topic_arg_group.add_argument("-t", "--topic", dest="topic",
                                 help="Topic to submit branch to")
    topic_arg_group.add_argument("-T", "--no-topic", dest="notopic",
                                 action="store_true",
                                 help="No topic except if explicitly provided")

    parser.add_argument("-D", "--draft", dest="draft", action="store_true",
                        help="Submit review as a draft")
    parser.add_argument("-c", "--compatible", dest="compatible",
                        action="store_true",
                        help="Push change to refs/for/* for compatibility "
                             "with Gerrit versions < 2.3. Ignored if "
                             "-D/--draft is used.")
    parser.add_argument("-n", "--dry-run", dest="dry", action="store_true",
                        help="Don't actually submit the branch for review")
    parser.add_argument("-i", "--new-changeid", dest="regenerate",
                        action="store_true",
                        help="Regenerate Change-id before submitting")
    parser.add_argument("-r", "--remote", dest="remote",
                        help="git remote to use for gerrit")

    rebase_group = parser.add_mutually_exclusive_group()
    rebase_group.add_argument("-R", "--no-rebase", dest="rebase",
                              action="store_false",
                              help="Don't rebase changes before submitting.")
    rebase_group.add_argument("-F", "--force-rebase", dest="force_rebase",
                              action="store_true",
                              help="Force rebase even when not needed.")

    fetch = parser.add_mutually_exclusive_group()
    fetch.set_defaults(download=False, compare=False, cherrypickcommit=False,
                       cherrypickindicate=False, cherrypickonly=False)
    fetch.add_argument("-d", "--download", dest="changeidentifier",
                       action=DownloadFlag, metavar="CHANGE",
                       const="download",
                       help="Download the contents of an existing gerrit "
                            "review into a branch")
    fetch.add_argument("-x", "--cherrypick", dest="changeidentifier",
                       action=DownloadFlag, metavar="CHANGE",
                       const="cherrypickcommit",
                       help="Apply the contents of an existing gerrit "
                             "review onto the current branch and commit "
                             "(cherry pick; not recommended in most "
                             "situations)")
    fetch.add_argument("-X", "--cherrypickindicate", dest="changeidentifier",
                       action=DownloadFlag, metavar="CHANGE",
                       const="cherrypickindicate",
                       help="Apply the contents of an existing gerrit "
                       "review onto the current branch and commit, "
                       "indicating its origin")
    fetch.add_argument("-N", "--cherrypickonly", dest="changeidentifier",
                       action=DownloadFlag, metavar="CHANGE",
                       const="cherrypickonly",
                       help="Apply the contents of an existing gerrit "
                       "review to the working directory and prepare "
                       "for commit")
    fetch.add_argument("-m", "--compare", dest="changeidentifier",
                       action=DownloadFlag, metavar="CHANGE,PS[-NEW_PS]",
                       const="compare",
                       help="Download specified and latest (or NEW_PS) "
                       "patchsets of an existing gerrit review into "
                       "a branches, rebase on master "
                       "(skipped on conflicts or when -R is specified) "
                       "and show their differences")

    parser.add_argument("-u", "--update", dest="update", action="store_true",
                        help="Force updates from remote locations")
    parser.add_argument("-s", "--setup", dest="setup", action="store_true",
                        help="Just run the repo setup commands but don't "
                             "submit anything")
    parser.add_argument("-f", "--finish", dest="finish", action="store_true",
                        help="Close down this branch and switch back to "
                             "master on successful submission")
    parser.add_argument("-l", "--list", dest="list", action="store_true",
                        help="List available reviews for the current project")
    parser.add_argument("-y", "--yes", dest="yes", action="store_true",
                        help="Indicate that you do, in fact, understand if "
                             "you are submitting more than one patch")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                        help="Output more information about what's going on")
    parser.add_argument("--no-custom-script", dest="custom_script",
                        action="store_false", default=True,
                        help="Do not run custom scripts.")
    parser.add_argument("--color", dest="color", metavar="<when>",
                        nargs="?", choices=["always", "never", "auto"],
                        help="Show color output. --color (without [<when>]) "
                             "is the same as --color=always. <when> can be "
                             "one of %(choices)s. Behaviour can also be "
                             "controlled by the color.ui and color.review "
                             "configuration settings.")
    parser.add_argument("--no-color", dest="color", action="store_const",
                        const="never",
                        help="Turn off colored output. Can be used to "
                             "override configuration options. Same as "
                             "setting --color=never.")
    parser.add_argument("--license", dest="license", action="store_true",
                        help="Print the license and exit")
    parser.add_argument("--version", action="version",
                        version='%s version %s' %
                        (os.path.split(sys.argv[0])[-1], get_version()))
    parser.add_argument("branch", nargs="?")

    parser.set_defaults(dry=False,
                        draft=False,
                        verbose=False,
                        update=False,
                        setup=False,
                        list=False,
                        yes=False)
    try:
        (top_dir, git_dir) = git_directories()
    except GitDirectoriesException as no_git_dir:
        pass
    else:
        no_git_dir = False
        config = Config(os.path.join(top_dir, ".gitreview"))
        parser.set_defaults(branch=config['branch'],
                            rebase=convert_bool(config['rebase']),
                            remote=config['remote'])
    options = parser.parse_args()
    if no_git_dir:
        raise no_git_dir

    if options.license:
        print(COPYRIGHT)
        sys.exit(0)

    branch = options.branch
    global VERBOSE
    global UPDATE
    VERBOSE = options.verbose
    UPDATE = options.update
    remote = options.remote
    yes = options.yes
    status = 0

    check_remote(branch, remote, config['scheme'],
                 config['hostname'], config['port'], config['project'])

    if options.color:
        set_color_output(options.color)

    if options.changeidentifier:
        if options.compare:
            compare_review(options.changeidentifier,
                           branch, remote, options.rebase)
            return
        local_branch = fetch_review(options.changeidentifier, branch, remote)
        if options.download:
            checkout_review(local_branch)
        else:
            if options.cherrypickcommit:
                cherrypick_review()
            elif options.cherrypickonly:
                cherrypick_review("-n")
            if options.cherrypickindicate:
                cherrypick_review("-x")
        return
    elif options.list:
        list_reviews(remote)
        return

    if options.custom_script:
        run_custom_script("pre")

    hook_file = os.path.join(git_dir, "hooks", "commit-msg")
    have_hook = os.path.exists(hook_file) and os.access(hook_file, os.X_OK)

    if not have_hook:
        set_hooks_commit_msg(remote, hook_file)

    if options.setup:
        if options.finish and not options.dry:
            finish_branch(branch)
        return

    if options.rebase or options.force_rebase:
        if not rebase_changes(branch, remote):
            sys.exit(1)
        if not options.force_rebase and not undo_rebase():
            sys.exit(1)
    assert_one_change(remote, branch, yes, have_hook)

    ref = "publish"

    if options.draft:
        ref = "drafts"
        if options.custom_script:
            run_custom_script("draft")
    elif options.compatible:
        ref = "for"

    cmd = "git push %s HEAD:refs/%s/%s" % (remote, ref, branch)
    if options.topic is not None:
        topic = options.topic
    else:
        topic = None if options.notopic else get_topic(branch)
    if topic and topic != branch:
        cmd += "/%s" % topic
    if options.regenerate:
        print("Amending the commit to regenerate the change id\n")
        regenerate_cmd = "git commit --amend"
        if options.dry:
            print("\tGIT_EDITOR=\"sed -i -e '/^Change-Id:/d'\" %s\n" %
                  regenerate_cmd)
        else:
            run_command(regenerate_cmd,
                        GIT_EDITOR="sed -i -e "
                        "'/^Change-Id:/d'")

    if options.dry:
        print("Please use the following command "
              "to send your commits to review:\n")
        print("\t%s\n" % cmd)
    else:
        (status, output) = run_command_status(cmd)
        print(output)

    if options.finish and not options.dry and status == 0:
        finish_branch(branch)
        return

    if options.custom_script:
        run_custom_script("post")
    sys.exit(status)


def main():
    try:
        _main()
    except GitReviewException as e:
        # If one does unguarded print(e) here, in certain locales the implicit
        # str(e) blows up with familiar "UnicodeEncodeError ... ordinal not in
        # range(128)". See rhbz#1058167.
        try:
            u = unicode(e)
        except NameError:
            # Python 3, we're home free.
            print(e)
        else:
            print(u.encode('utf-8'))
        sys.exit(e.EXIT_CODE)


if __name__ == "__main__":
    main()
