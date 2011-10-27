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

If you want to skip the automatic "git rebase -i" step:

    git review -R

If you want to download change 781 from gerrit to review it:

    git review -d 781

## Contributing

To get the latest code or for information about contributing, visit
the project homepage at:

  https://launchpad.net/git-review
