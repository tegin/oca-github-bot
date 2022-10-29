# Copyright (c) ForgeFlow, S.L. 2021
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

import shutil
import tempfile

import copier
from github3.exceptions import NotFoundError

from .. import config, github
from ..config import switchable
from ..github import github_user_can_push
from ..process import CalledProcessError, check_call
from ..queue import task
from ..utils import hide_secrets


@task()
@switchable("new_repo")
def new_repo(org, repo, pr, username, new_repo_name, team, dry_run=False):
    with github.login() as gh:
        gh_pr = gh.issue(org, repo, pr)
        gh_repo = gh.repository(org, repo)
        if not github_user_can_push(gh_repo, username):
            github.gh_call(
                gh_pr.create_comment,
                f"Sorry @{username} you are not allowed to " "create a new repo ",
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
        gh_new_repo = gh_org.create_repository(
            new_repo_name, new_repo_name, team_id=gh_team.id
        )
        try:
            clone_dir = tempfile.mkdtemp()
            copier.run_auto(
                config.NEW_REPO_TEMPLATE,
                clone_dir,
                defaults=True,
                data={
                    "repo_name": new_repo_name,
                    "repo_slug": new_repo_name,
                },
            )
            check_call(
                ["git", "init"],
                cwd=clone_dir,
            )
            if config.GIT_NAME:
                check_call(
                    ["git", "config", "user.name", config.GIT_NAME], cwd=clone_dir
                )
            if config.GIT_EMAIL:
                check_call(
                    ["git", "config", "user.email", config.GIT_EMAIL], cwd=clone_dir
                )
            check_call(
                ["git", "add", "-A"],
                cwd=clone_dir,
            )
            check_call(
                ["git", "commit", "-m", "Initial commit"],
                cwd=clone_dir,
            )
            check_call(
                ["git", "checkout", "-b", config.NEW_REPO_VERSION],
                cwd=clone_dir,
            )
            check_call(
                ["git", "remote", "add", "origin", gh_new_repo.url],
                cwd=clone_dir,
            )
            check_call(
                [
                    "git",
                    "remote",
                    "set-url",
                    "--push",
                    "origin",
                    f"https://{config.GITHUB_TOKEN}@github.com/{org}/{new_repo_name}",
                ],
                cwd=clone_dir,
            )
            check_call(
                ["git", "push", "origin", config.NEW_REPO_VERSION],
                cwd=clone_dir,
            )
        except CalledProcessError as e:
            cmd = " ".join(e.cmd)
            github.gh_call(
                gh_pr.create_comment,
                hide_secrets(
                    f"@{username} The creation process failed, because "
                    f"command `{cmd}` failed with output:\n```\n{e.output}\n```"
                ),
            )
            raise
        finally:
            shutil.rmtree(clone_dir)
        github.gh_call(
            gh_pr.create_comment,
            f"Thanks @{username} new repo "
            "[{new_repo_name}](https://github.com/{org}/{new_repo_name}) "
            "has been created.",
        )
        gh_pr.close()
