# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

import re

from . import config
from .tasks import add_psc_member_bot, merge_bot, migration_issue_bot, rebase_bot

BOT_COMMAND_RE = re.compile(
    # Do not start with > (Github comment), not consuming it
    r"^(?=[^>])"
    # Anything before /ocabot, at least one whitspace after
    r".*/ocabot\s+"
    # command group: any word is ok
    r"(?P<command>\w+)"
    # options group: spaces and words, all the times you want (0 is ok too)
    r"(?P<options>[ \t\w]*)"
    # non-capturing group:
    # stop finding options as soon as you find something that is not a word
    r"(?:\W|\r?$)",
    re.MULTILINE,
)


class CommandError(Exception):
    pass


class InvalidCommandError(CommandError):
    def __init__(self, name):
        super().__init__(f"Invalid command: {name}")


class OptionsError(CommandError):
    pass


class InvalidOptionsError(OptionsError):
    def __init__(self, name, options):
        options_text = " ".join(options)
        super().__init__(f"Invalid options for command {name}: {options_text}")


class RequiredOptionError(OptionsError):
    def __init__(self, name, option, values):
        values_text = ", ".join(values)
        super().__init__(
            f"Required option {option} for command {name}.\n"
            f"Possible values : {values_text}"
        )


class BotCommand:
    def __init__(self, name, options):
        self.name = name
        self.options = options
        self.parse_options(options)

    @classmethod
    def create(cls, name, options, repo, is_pull_request):
        if name == "merge" and is_pull_request:
            return BotCommandMerge(name, options)
        elif name == "rebase" and is_pull_request:
            return BotCommandRebase(name, options)
        elif name == "migration" and is_pull_request:
            return BotCommandMigrationIssue(name, options)
        elif is_pull_request:
            raise InvalidCommandError(name)
        elif name == "add_psc" and repo == config.GITHUB_PSC_REPO:
            return BotCommandAddPSC(name, options)
        return None

    def parse_options(self, options):
        pass

    def delay(self, org, repo, pr, username, dry_run=False):
        """Run the command on a given pull request on behalf of a GitHub user"""
        raise NotImplementedError()


class BotCommandMerge(BotCommand):
    bumpversion_mode = None
    bumpversion_mode_list = ["major", "minor", "patch", "nobump"]

    def parse_options(self, options):
        if not options:
            raise RequiredOptionError(
                self.name, "bumpversion_mode", self.bumpversion_mode_list
            )
        if len(options) == 1 and options[0] in self.bumpversion_mode_list:
            self.bumpversion_mode = options[0]
        else:
            raise InvalidOptionsError(self.name, options)

    def delay(self, org, repo, pr, username, dry_run=False):
        merge_bot.merge_bot_start.delay(
            org, repo, pr, username, self.bumpversion_mode, dry_run=False
        )


class BotCommandRebase(BotCommand):
    def parse_options(self, options):
        if not options:
            return
        raise InvalidOptionsError(self.name, options)

    def delay(self, org, repo, pr, username, dry_run=False):
        rebase_bot.rebase_bot_start.delay(org, repo, pr, username, dry_run=False)


class BotCommandAddPSC(BotCommand):
    team = None  # mandatory str: team name

    def parse_options(self, options):
        if len(options) == 1:
            self.team = options[0]
        else:
            raise InvalidOptionsError(self.name, options)

    def delay(self, org, repo, pr, username, dry_run=False):
        add_psc_member_bot.add_psc_member.delay(
            org, repo, pr, username, team=self.team, dry_run=dry_run
        )


class BotCommandMigrationIssue(BotCommand):
    module = None  # mandatory str: module name

    def parse_options(self, options):
        if len(options) == 1:
            self.module = options[0]
        else:
            raise InvalidOptionsError(self.name, options)

    def delay(self, org, repo, pr, username, dry_run=False):
        migration_issue_bot.migration_issue_start.delay(
            org, repo, pr, username, module=self.module, dry_run=dry_run
        )


def parse_commands(text, repo, is_pull_request):
    """Parse a text and return an iterator of BotCommand objects."""
    for mo in BOT_COMMAND_RE.finditer(text):
        command = BotCommand.create(
            mo.group("command"),
            mo.group("options").strip().split(),
            repo,
            is_pull_request,
        )
        if command is not None:
            yield command
