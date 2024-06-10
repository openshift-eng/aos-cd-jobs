#!/usr/bin/env python3

import json
import os
import time
import requests
import sys
from datetime import datetime, timezone
from collections import OrderedDict
from urllib.parse import unquote

from slack_bolt import App
from slack_sdk.errors import SlackApiError

SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN')
SLACK_SIGNING_SECRET = os.getenv('SLACK_SIGNING_SECRET')
USER_TOKEN = os.getenv('SLACK_USER_TOKEN')
CHANNEL = os.getenv('CHANNEL')
JENKINS_TOKEN = os.getenv('JENKINS_SERVICE_ACCOUNT_TOKEN')
JENKINS_USER = os.getenv('JENKINS_SERVICE_ACCOUNT')
JENKINS_URL = os.getenv('JENKINS_URL').rstrip('/')

RELEASE_ARTIST_HANDLE = 'release-artists'

def get_failed_jobs_text():
    aos_cd_builds_url = f"{JENKINS_URL}/job/aos-cd-builds"
    api_url = f"{aos_cd_builds_url}/api/json"
    query = "?tree=jobs[name,builds[number,result,timestamp]]"  # status,displayName are also useful
    response = requests.get(api_url+query, auth=(JENKINS_USER, JENKINS_TOKEN))
    response.raise_for_status()
    data = response.json()
    failed_jobs = []
    now = datetime.now(timezone.utc)
    for job in data['jobs']:
        job_name = job['name']
        f = 0
        for build in job['builds']:
            dt = datetime.fromtimestamp(build['timestamp']/1000, tz=timezone.utc)
            td = now - dt
            hours = td.seconds//3600
            minutes = (td.seconds//60)%60
            if not (td.days == 0 and hours < 3):
                continue
            if build['result'] == 'FAILURE':
                f += 1
        if f > 0:
            failed_jobs.append((job_name, f))

    def job_link(job_name):
        link = f"{aos_cd_builds_url}/job/{job_name}/"
        return f"<{link}|{unquote(job_name)}>"

    if failed_jobs:
        failed_jobs.sort(key=lambda x: x[1], reverse=True)
        failed_jobs_list = "\n".join([f"* {job_link(job[0])}: {job[1]}" for job in failed_jobs])
        failed_jobs_text = f"Failed aos-cd-jobs in last 3 hours: \n{failed_jobs_list}"
        return failed_jobs_text
    return ''

def main():
    failed_jobs_text = get_failed_jobs_text()

    app = App(
        token=SLACK_API_TOKEN,
        signing_secret=SLACK_SIGNING_SECRET,
    )

    all_matches = []
    next_cursor = '*'
    while next_cursor:
        # https://api.slack.com/methods/search.messages#examples
        slack_response = app.client.search_messages(
            token=USER_TOKEN,
            query='has::art-attention: -has::art-attention-resolved:',
            cursor=next_cursor
        )
        messages = slack_response.get('messages', {})
        all_matches.extend(messages.get('matches', []))

        # https://api.slack.com/docs/pagination
        response_metadata = slack_response.get('response_metadata', {})
        next_cursor = response_metadata.get('next_cursor', None)

    all_matches = sorted(all_matches, key=lambda m: m.get('ts', '0.0'))

    if not (all_matches or failed_jobs_text):
        print('No messages matching attention emoji criteria and no failed jobs found')
        response = app.client.chat_postMessage(
            channel=CHANNEL,
            text=f':check: no unresolved threads / job failures found'
        )
        exit(0)

    print(json.dumps(all_matches))

    header_text = "Currently unresolved ART threads"
    fallback_text = header_text

    response_messages = []
    channel_warnings = {}
    current_epoch_time = time.time()
    for match in all_matches:
        team_id = match.get('team', '')
        channel_id = match.get('channel', {}).get('id', '')
        channel_name = match.get('channel', {}).get('name', 'Unknown')
        channel_handle = f'<https://redhat-internal.slack.com/archives/{channel_id}|#{channel_name}>'
        if len(channel_id) > 0:
            try:
                conv_info = app.client.conversations_info(channel=channel_id)

            except SlackApiError:
                msg = f':warning: Found an unresolved thread in channel {channel_handle}' \
                      f' but the channel is not accessible by the bot. Please invite <@art-bot> to {channel_handle}'
                if not channel_warnings.get(channel_id, None):
                    channel_warnings[channel_id] = msg
                continue

            channel_name = conv_info.get('channel', {}).get('name_normalized', channel_name)
        text = match.get('text', 'Link')
        permalink = match.get('permalink', None)
        if not permalink:
            permalink = 'about:blank'
            text = json.dumps(match)

        fallback_text += f'\n{permalink}'
        timestamp = int(float(match.get('ts', '0.0')))
        str_date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        age = current_epoch_time - timestamp
        age_type = 'seconds'
        if age > 120:
            age /= 60
            age_type = 'minutes'

            if age >= 60:
                age /= 60
                age_type = 'hours'

                if age >= 48:
                    age /= 24
                    age_type = 'days'

        age = int(age)
        # Block builder: https://app.slack.com/block-kit-builder/T04714LEPHA#%7B%22blocks%22:%5B%5D%7D
        snippet = ' '.join(text.split(' ')[0:30])
        # Slack includes an arrow character in the text if should be replaced by rich text elements (e.g. a n@username).
        # We just remove them since we are just trying for a short summary.
        snippet = snippet.replace('\ue006', '...')
        response_messages.append(
            f"*Channel:* {channel_handle}\n*Date:* {str_date}Z\n*Age:* {age} {age_type}\n*Message:* <{permalink}|Link>\n*Snippet:* {snippet}...")

    header_block = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{header_text} ({len(response_messages)})",
                "emoji": True
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Attention @{RELEASE_ARTIST_HANDLE}"
            }
        }
    ]

    # https://api.slack.com/methods/chat.postMessage#examples
    response = app.client.chat_postMessage(channel=CHANNEL,
                                           text=f'@{RELEASE_ARTIST_HANDLE} - {fallback_text}',
                                           blocks=header_block,
                                           unfurl_links=False)

    # Post warnings about inaccessible channels first
    for warning in channel_warnings.values():
        app.client.chat_postMessage(channel=CHANNEL,
                                    text=warning,
                                    thread_ts=response['ts'])

    for response_message in response_messages:
        app.client.chat_postMessage(channel=CHANNEL,
                                    text=response_message,
                                    thread_ts=response['ts'])  # use the timestamp from the response

    if failed_jobs_text:
        app.client.chat_postMessage(channel=CHANNEL,
                                    text=failed_jobs_text,
                                    thread_ts=response['ts'])

if __name__ == '__main__':
    main()
