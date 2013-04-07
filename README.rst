git-review
==========

A git command for submitting branches to Gerrit

git-review is a tool that helps submitting git branches to gerrit for
review.

Setup
-----

git-review, by default, looks for a git remote called gerrit, and
submits the current branch to HEAD:refs/for/master at that remote.

If the "gerrit" remote does not exist, git-review looks for a file
called .gitreview at the root of the repository with information about
the gerrit remote.  Assuming that file is present, git-review should
be able to automatically configure your repository the first time it
is run.

Usage
-----

Hack on some code, then::

    git review

If you want to submit that code to a branch other than "master", then::

    git review branchname

If you want to submit to a different remote::

    git review -r my-remote

If you want to supply a review topic::

    git review -t topic/awesome-feature

If you want to submit a branch for review and then remove the local branch::

    git review -f

If you want to skip the automatic "git rebase -i" step::

    git review -R

If you want to download change 781 from gerrit to review it::

    git review -d 781

If you want to download patchset 4 for change 781 from gerrit to review it::

    git review -d 781,4

If you want to compare patchset 4 with patchset 10 of change 781 from gerrit::

    git review -m 781,4-10

If you just want to do the commit message and remote setup steps::

    git review -s

.gitreview file format
----------------------

Example .gitreview file (used to upload for git-review itself)::

    [gerrit]
    host=review.openstack.org
    port=29418
    project=openstack-infra/git-review.git
    defaultbranch=master

Required values: host, project

Optional values: port (default: 29418), defaultbranch (default: master)

**Notes**

* Username not required because it is requested on first run

* Unlike git config files there cannot be any whitespace before the name of the variable.

* git-review will create a gerrit remote upon first run

Hooks
-----

git-review has a custom hook mechanism to run a script before certain
actions. This is done in the same spirit as the classic hooks in git.

There are two types of hooks, a global one which is stored in
~/.config/git-review/hooks/ and one local to the repository stored in
.git/hooks/ with the other git hook scripts.

**The script needs be executable before getting executed**

The name of the script is $action-review where action can be
:

* pre - run at first before doing anything.

* post - run at the end after the review was sent.

* draft - run when in draft mode.

if the script returns with an exit status different than zero,
git-review will exit with the a custom shell exit code 71.

Installation
------------

Install with pip install git-review

For installation from source simply add git-review to your $PATH

Contributing
------------

To get the latest code, see: https://github.com/openstack-infra/git-review

Bugs are handled at: https://launchpad.net/git-review

There is a mailing list at: http://lists.openstack.org/cgi-bin/mailman/listinfo/openstack-infra

Code reviews, as you might expect, are handled by gerrit at: https://review.openstack.org

Use ``git review`` to submit patches (after creating a gerrit account that links to your launchpad account). Example::

    # Do your commits
    git review
    # Enter your username if promped
