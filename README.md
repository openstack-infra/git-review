# git-review

A git command for submitting branches to Gerrit

git-review is a tool that helps submitting git branches to gerrit for
review.

## Setup

git-review, by default, looks for a git remote called gerrit, and
submits the current branch to HEAD:refs/for/master at that remote.

If the "gerrit" remote does not exist, git-review looks for a file
called .gitreview at the root of the repository with information about
the gerrit remote.  Assuming that file is present, git-review should
be able to automatically configure your repository the first time it
is run.

## Usage

Hack on some code, then:

    git review

If you want to submit that code to a branch other than "master", then:

    git review branchname

If you want to submit to a different remote:

    git review -r my-remote

If you want to supply a review topic:

    git review -t topic/awesome-feature

If you want to submit a branch for review and then remove the local branch:

    git review -f

If you want to skip the automatic "git rebase -i" step:

    git review -R

If you want to download change 781 from gerrit to review it:

    git review -d 781

If you just want to do the commit message and remote setup steps:

    git review -s

## Contributing

To get the latest code, see:

    https://github.com/openstack-ci/git-review

Bugs are handled at:

    https://launchpad.net/git-review

Code reviews are, as you might expect, handled by gerrit. The gerrit they
use is http://review.openstack.org. Use git review to submit patches.
submit them.
