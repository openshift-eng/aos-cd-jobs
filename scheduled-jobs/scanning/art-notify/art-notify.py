#!/usr/bin/env python3

import json
import os
import time
import requests
from datetime import datetime, timezone
from urllib.parse import unquote, quote

from slack_bolt import App
from slack_sdk.errors import SlackApiError

from check_expired_certificates import check_expired_certificates

SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN')
SLACK_SIGNING_SECRET = os.getenv('SLACK_SIGNING_SECRET')
USER_TOKEN = os.getenv('SLACK_USER_TOKEN')
CHANNEL = os.getenv('CHANNEL')
DRY_RUN = os.getenv('DRY_RUN')
JENKINS_TOKEN = os.getenv('JENKINS_SERVICE_ACCOUNT_TOKEN')
JENKINS_USER = os.getenv('JENKINS_SERVICE_ACCOUNT')
JENKINS_URL = os.getenv('JENKINS_URL').rstrip('/')

RELEASE_ARTIST_HANDLE = 'release-artists'
ART_BOT_JENKINS_USERID = 'openshift-art'  # userId of our automation account in jenkins which triggers builds
FAILED_JOB_HOURS = 8  # Last x hours that we consider for our failed job search


def get_failed_jobs_text():
    projects = ["aos-cd-builds", "scheduled-builds"]
    failed_jobs = []
    # API reference
    # for a job: <jenkins_url>/job/<project>/job/<job_name>/api/json?pretty=true
    # for a build: <jenkins_url>/job/<project>/job/<job_name>/<build_number>/api/json?pretty=true
    query = "?tree=jobs[name,url,builds[number,result,timestamp,actions[causes[userId]]]]"
    now = datetime.now(timezone.utc)
    for project in projects:
        api_url = f"{JENKINS_URL}/job/{project}/api/json"
        response = requests.get(api_url + query, auth=(JENKINS_USER, JENKINS_TOKEN))
        response.raise_for_status()
        data = response.json()
        for job in data['jobs']:
            if 'builds' not in job:
                continue
            job_name = job['name']
            failed_job_ids = []
            total_eligible_builds = 0
            for build in job['builds']:
                dt = datetime.fromtimestamp(build['timestamp'] / 1000, tz=timezone.utc)
                td = now - dt
                hours = td.seconds // 3600
                minutes = (td.seconds // 60) % 60
                if not (td.days == 0 and hours < FAILED_JOB_HOURS):
                    continue
                # Filter all builds that were not triggered by our automation account
                # We do not want to report on these since they are manually triggered and
                # would be monitored by whoever triggered them
                # Builds which are triggered by another build will not have userId
                # so we include them by default
                user_id = next(a['causes'][0].get('userId') for a in build.get('actions') if a.get('causes'))
                if user_id and user_id != ART_BOT_JENKINS_USERID:
                    continue
                total_eligible_builds += 1
                if build['result'] == 'FAILURE':
                    failed_job_ids.append(build['number'])
            if len(failed_job_ids) > 0:
                fail_rate = (len(failed_job_ids)/total_eligible_builds)*100
                failed_jobs.append((unquote(job_name), failed_job_ids, fail_rate, job['url']))
        
    def slack_link(job_name, job_url, job_id=None, text=None):
        link = job_url
        if job_id:
            link += f"{job_id}/console"
        if not text:
            if job_id:
                text = f"#{job_id}"
            else:
                text = unquote(job_name)
        return f"<{link}|{text}>"

    if failed_jobs:
        failed_jobs.sort(key=lambda x: x[2], reverse=True)
        failed_jobs_list = []
        for job_name, failed_job_ids, fail_rate, job_url in failed_jobs:
            link = slack_link(job_name, job_url)
            text = f"* {link}: {len(failed_job_ids)} "
            failed_job_ids.sort(reverse=True)
            for i in range(min(3, len(failed_job_ids))):
                text += f"[{slack_link(job_name, job_url, job_id=failed_job_ids[i], text=i+1)}] "
            text += f"Fail rate: {fail_rate:.1f}%"
            failed_jobs_list.append(text)
        failed_jobs_list = "\n".join(failed_jobs_list)
        failed_jobs_text = f"Failed builds in last `{FAILED_JOB_HOURS}` hours triggered by `{ART_BOT_JENKINS_USERID}`: \n{failed_jobs_list}"
        return failed_jobs_text
    return ''


def message_to_slack(app, channel, text, thread_ts=None):
    pass


def main():
    failed_jobs_text = get_failed_jobs_text()
    expired_certificates = check_expired_certificates()

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

    if DRY_RUN.lower() == "true":
        print("[DRY RUN] Would have messaged to Slack")

        for warning in channel_warnings.values():
            print(warning)

        for response_message in response_messages:
            print(response_message)

        if failed_jobs_text:
            print(failed_jobs_text)

        if expired_certificates:
            print(expired_certificates)
    else:
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

        if expired_certificates:
            app.client.chat_postMessage(channel=CHANNEL,
                                        text=expired_certificates,
                                        thread_ts=response['ts'])


if __name__ == '__main__':
    main()
