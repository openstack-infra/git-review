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

  git -r my-remote review


