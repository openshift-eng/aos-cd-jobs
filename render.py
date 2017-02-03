#!/usr/bin/env python3

from jinja2 import Environment, FileSystemLoader
from os.path import abspath, dirname, join
import sys

template_dir = abspath(join(dirname(__file__), 'templates'))
template = sys.argv[1] + '.j2'
context = {}
if len(sys.argv) > 2:
	for arg in sys.argv[2:]:
		key, value = arg.split('=', 1)
		context[key] = value

env = Environment(loader=FileSystemLoader(template_dir))
env.globals=context

print(env.get_template(template).render())