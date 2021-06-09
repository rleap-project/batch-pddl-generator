#! /usr/bin/env python

import ast
import collections
import logging
import re

from lab.parser import Parser


class CommonParser(Parser):
    def _get_flags(self, flags_string):
        flags = 0
        for char in flags_string:
            flags |= getattr(re, char)
        return flags

    def add_repeated_pattern(
            self, name, regex, file="run.log", required=False, type=int,
            flags="", group=None):
        flags += "M"

        def find_all_occurences(content, props):
            matches = re.findall(regex, content, flags=self._get_flags(flags))
            if required and not matches:
                logging.error("Pattern {0} not found in file {1}".format(regex, file))
            props[name] = [type(m if group is None else m[group]) for m in matches]

        self.add_function(find_all_occurences, file=file)

    def add_bottom_up_pattern(self, name, regex, file="run.log", required=False, type=int, flags=""):

        def search_from_bottom(content, props):
            reversed_content = "\n".join(reversed(content.splitlines()))
            match = re.search(regex, reversed_content, flags=self._get_flags(flags))
            if required and not match:
                logging.error("Pattern {0} not found in file {1}".format(regex, file))
            if match:
                props[name] = type(match.group(1))

        self.add_function(search_from_bottom, file=file)


def error(content, props):
    if props.get('smac_exit_code') == 0:
        props['error'] = 'none'
    else:
        props['error'] = 'some-error-occured'


def parse_runtimes(content, props):
    baseline_runtimes = []
    sart_runtimes = []
    for line in content.splitlines():
        match = re.match(r".*(sart|baseline) runtime for y=(.+): (.*)", line)
        if match:
            name, config_string, value_string = match.groups()
            parameters = ast.literal_eval(config_string)
            runtimes = ast.literal_eval(value_string)

            if name == "sart":
                sart_runtimes.append((parameters, runtimes))
            else:
                baseline_runtimes.append((parameters, runtimes))
    props["baseline_runtimes"] = baseline_runtimes
    props["sart_runtimes"] = sart_runtimes


def parse_shared_runs(content, props):
    values = re.findall(r"Shared model mode: Finished loading new runs, found (.+) new runs.", content)
    props["max_shared_runs"] = max(int(val) for val in values) if values else -1


def unsolvable(content, props):
    props["unsolvable"] = int(
        ("unsolvable" in content.lower()) and
        ("Abstract problem is unsolvable or time limit reached!" not in content.lower()))


parser = CommonParser()
parser.add_pattern(
    'node', r'node: (.+)\n', type=str, file='driver.log', required=True)
parser.add_pattern(
    'smac_exit_code', r'generate exit code: (.+)\n', type=int, file='driver.log')
parser.add_repeated_pattern('sequences', r'Sequence: (.+)\n', type=str)
parser.add_bottom_up_pattern('final_sequence', r'Final sequence: (\{.+\})\n', type=str)
parser.add_bottom_up_pattern('final_baseline_runtimes', r'Final baseline runtimes: (.*)\n', type=str)
parser.add_bottom_up_pattern('final_sart_runtimes', r'Final sart runtimes: (.*)\n', type=str)
parser.add_bottom_up_pattern('final_value', r'Estimated cost of incumbent: (.+)\n', type=float)
parser.add_bottom_up_pattern('evaluated_configurations', r'\#Configurations: (\d+)\n', type=int)
parser.add_bottom_up_pattern('incumbent_changed', r'\#Incumbent changed: (.+)\n', type=int)
parser.add_bottom_up_pattern('evaluation_time', r'Used target algorithm runtime: (.+) / .+ sec', type=float)
parser.add_bottom_up_pattern('wallclock_time', r'Used wallclock time: (.+) / .+ sec', type=float)
parser.add_bottom_up_pattern('memory', r'\[(\d+) KB\]', type=int)
parser.add_bottom_up_pattern('memory_subsequences', r'Previous subsequences: \d+, (.+) KB', type=float)
parser.add_bottom_up_pattern('memory_baseline_runner', r'baseline runner memory: (.+) KB', type=float)
parser.add_bottom_up_pattern('memory_sart_runner', r'sart runner memory: (.+) KB', type=float)
parser.add_function(error)
parser.add_function(parse_runtimes)
parser.add_function(parse_shared_runs)
parser.add_function(unsolvable)

parser.parse()
