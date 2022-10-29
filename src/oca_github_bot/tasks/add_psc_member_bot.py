# Copyright (c) ForgeFlow, S.L. 2021
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

from github3.exceptions import NotFoundError

from .. import github
from ..config import switchable
from ..github import github_user_can_push
from ..queue import task


@task()
@switchable("add_psc_member")
def add_psc_member(org, repo, pr, username, team, dry_run=False):
    with github.login() as gh:
        gh_pr = gh.issue(org, repo, pr)
        gh_repo = gh.repository(org, repo)
        if not github_user_can_push(gh_repo, username):
            github.gh_call(
                gh_pr.create_comment,
                f"Sorry @{username} you are not allowed to "
                "launch the change of the PSC ",
            )
            return
        gh_org = gh.organization(org)
        try:
            gh_team = gh_org.team_by_name(team)
        except NotFoundError:
            github.gh_call(
                gh_pr.create_comment,
                f"Sorry @{username} team @{org}/{team} was not found",
            )
            return
        gh_team.add_or_update_membership(gh_pr.user)
        github.gh_call(
            gh_pr.create_comment,
            f"Thanks @{username} You have been added to @{org}/{team}.",
        )
        gh_pr.close()
