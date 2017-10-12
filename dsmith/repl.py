#
# Copyright 2017 Chris Cummins <chrisc.101@gmail.com>.
#
# This file is part of DeepSmith.
#
# DeepSmith is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# DeepSmith is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# DeepSmith.  If not, see <http://www.gnu.org/licenses/>.
#
"""
Parser for dsmith

Attributes:
    __help__ (str): REPL help string.
    __available_commands__ (str): Help string for available commands.
"""
import random
import datetime
import logging
import re
import sys

from collections import namedtuple

import dsmith

class Colors:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

_lang_str = f"{Colors.RED}<lang>{Colors.END}{Colors.BOLD}"
_generator_str = f"{Colors.GREEN}<generator>{Colors.END}{Colors.BOLD}"
_testbed_str = f"{Colors.PURPLE}<testbed>{Colors.END}{Colors.BOLD}"
_num_str = f"{Colors.BLUE}<number>{Colors.END}{Colors.BOLD}"

__available_commands__ = f"""\
  {Colors.BOLD}describe [all]{Colors.END}
    Provide an overview of stored data.

  {Colors.BOLD}describe {_lang_str} {{\
{Colors.GREEN}generators{Colors.END}{Colors.BOLD},\
{Colors.PURPLE}testbeds{Colors.END},\
programs,testcases,results}}{Colors.END}
    Provide details about available generators, testbeds, generated
    programs, testcases, or results.

  {Colors.BOLD}make [{_num_str}] {_lang_str} programs [using {_generator_str}]{Colors.END}
    Generate programs. If no generator is specified, default to dsmith.

  {Colors.BOLD}make {_lang_str} [{_generator_str}] testcases{Colors.END}
    Prepare testcases from programs.

  {Colors.BOLD}run {_lang_str} [{_generator_str}] testcases [on {_testbed_str}] [{{with,without}} optimizations]{Colors.END}
    Run testcases. If no generator is specified, run testcases from all
    generators. If no testbed is specified, use all available
    testbeds. If optimizations are not specified, run both.

  {Colors.BOLD}difftest {_lang_str} [{_generator_str}] results{Colors.END}
    Compare results across devices.

  {Colors.BOLD}exit{Colors.END}
    End the session.\
"""


__help__ = f"""\
This is the DeepSmith interactive session. The following commands are available:

{__available_commands__}
"""


class UnrecognizedInput(ValueError):
    pass


def _help_func(*args, **kwargs):
    file = kwargs.pop("file", sys.stdout)
    print(__help__, file=file)


def _exit_func(*args, **kwargs):
    file = kwargs.pop("file", sys.stdout)

    farewell = random.choice([
        "Have a nice day!",
        "Over and out.",
        "God speed.",
        "See ya!",
        "See you later alligator.",
    ])
    print(f"{Colors.END}{farewell}", file=file)
    sys.exit()


def _describe_func(*args, **kwargs):
    raise NotImplementedError


def _make_func(*args, **kwargs):
    raise NotImplementedError


def _run_func(*args, **kwargs):
    raise NotImplementedError


def _difftest_func(*args, **kwargs):
    raise NotImplementedError


class ParsedStatement(object):
    """
    A parsed statement.
    """
    def __init__(self, statement: str):
        self.statement = statement
        self.msg = None
        self.func = None
        self.args = []
        self.kwargs = {}


def parse(statement: str) -> ParsedStatement:
    if not isinstance(statement, str): raise TypeError

    parsed = ParsedStatement(statement)

    # parsing is case insensitive
    statement = re.sub("\s+", " ", statement.strip().lower())
    components = statement.split(" ")

    csv = ", ".join(f"'{x}'" for x in components)
    logging.debug(f"parsing input [{csv}]")

    if not statement:
        return parsed

    if len(components) == 1 and re.match(r'(hi|hello|hey)', components[0]):
        parsed.msg = "Hi there!"
    elif len(components) == 1 and re.match(r'(exit|quit)', components[0]):
        parsed.func = _exit_func
    elif len(components) < 3 and components[0] == "help":
        parsed.func = _help_func
        parsed.args = components[1:]
    elif components[0] == "describe":
        parsed.func = _describe_func
        parsed.args = components[1:]
    elif components[0] == "make":
        parsed.func = _make_func
        parsed.args = components[1:]
    elif components[0] == "run":
        parsed.func = _run_func
        parsed.args = components[1:]
    elif components[0] == "difftest":
        parsed.func = _difftest_func
        parsed.args = components[1:]
    else:
        raise UnrecognizedInput("😕  I don't understand. "
                                "Type 'help' for available commands.")

    return parsed


def repl(file=sys.stdout) -> None:
    hour = datetime.datetime.now().hour

    greeting = "Good evening."
    if hour > 4:
        greeting = "Good morning."
    if hour > 12 and hour < 18:
        greeting = "Good afternoon."

    print(greeting, "Type 'help' for available commands.", file=file)

    try:
        while True:
            sys.stdout.write(f"{Colors.BOLD}> ")
            choice = input()
            sys.stdout.write(Colors.END)
            sys.stdout.flush()

            try:
                parsed = parse(choice)

                if parsed.msg:
                    print(parsed.msg, file=file)

                if parsed.func:
                    args = ", ".join(f"'{x}'" for x in parsed.args)
                    kwargs = ""
                    debug_msg = f"func = {parsed.func.__name__}, args = [{args}], kwargs = {{{kwargs}}}"

                    logging.debug(debug_msg)
                    parsed.func(*parsed.args, **parsed.kwargs)
            except UnrecognizedInput as e:
                print(e, file=file)
            except NotImplementedError:
                print("🤔  I don't know how to do that (yet).", file=file)

    except KeyboardInterrupt:
        print("", file=file)
        _exit_func(file=file)
