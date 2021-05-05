#!/usr/bin/env python3

import click
import pathlib
import sys
import json


@click.command()
@click.option('--record-log', multiple=True, required=True, help='Path to the record.log file to parse')
@click.option('--output', default=None, help='Output file (if not specified, stdout will be used)')
def convert(record_log, output):
    if output:
        sink = open(output, mode='w')
    else:
        sink = sys.stdout

    sink.write('|Component|Build Stage|Issues Count|Report|Data|Issue Types|\n')
    sink.write('|---|---|---|---|---|---|\n')
    for record_log_file in record_log:
        with open(record_log_file, mode='r') as rl:
            for line in rl.readlines():
                fields = line.split('|')
                record_type = fields[0]
                attributes = dict()
                for field in fields[1:]:
                    field = field.strip()
                    if not field:
                        continue
                    k, v = field.split('=', 1)
                    v = v.replace(';;;', '\n')
                    attributes[k] = v

                if record_type == 'covscan':
                    component = attributes['distgit_key']
                    build_stage = attributes['stage_number']
                    commit_hash = attributes['commit_hash']
                    all_results_js_path = pathlib.Path(attributes['all_results_js_path'])
                    all_results = json.loads(all_results_js_path.read_text(encoding='utf-8'))
                    issues = all_results.get('issues', [])
                    count = len(issues)
                    types = set()
                    for issue in issues:
                        types.add(issue['checkerName'])
                    report_url = f'http://download.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/coverity/results/{component}/{commit_hash}/stage_{build_stage}/all_results.html'
                    data_url = f'http://download.eng.bos.redhat.com/rcm-guest/puddles/RHAOS/coverity/results/{component}/{commit_hash}/stage_{build_stage}/all_results.js'
                    sink.write(f'|{component}|{build_stage}|{count}|[Report]({report_url})|[Data]({data_url})|{", ".join(types)}|\n')

    if sink != sys.stdout:
        sink.close()


if __name__ == '__main__':
    convert()
