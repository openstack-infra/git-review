# git-review: A git command for submitting branches to Gerrit

git-review is a tool that helps submitting git branches to gerrit for review

# Assumptions

git-review, by default, looks for a git remote called gerrit, and submits
the current branch to HEAD:refs/for/master at that remote.

# Usage

Hack on some code, then:

  git review

If you want to submit that code to a different target branch, then:

  git review branchname

If you want to submit to a different remote:

  git review -r my-remote

If you want to supply a review topic:

  git review -t topic/awesome-feature

If you want to submit your change to a branch other than master:

  git review milestone-proposed

If you want to skip the automatic rebase -i step:

  git review -R

If you want to download change 781 from gerrit to review it:

  git review -d 781
