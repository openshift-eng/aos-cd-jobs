#!/usr/bin/env python3

import json
import os
import time
import datetime

from slack_bolt import App

SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN')
SLACK_SIGNING_SECRET = os.getenv('SLACK_SIGNING_SECRET')
USER_TOKEN = os.getenv('SLACK_USER_TOKEN')

TEAM_ART_CHANNEL = 'team-art'
RELEASE_ARTIST_HANDLE = 'release-artists'

if __name__ == '__main__':
    app = App(
        token=SLACK_API_TOKEN,
        signing_secret=SLACK_SIGNING_SECRET,
    )

    all_matches = []
    next_cursor = '*'
    while next_cursor:
        # https://api.slack.com/methods/search.messages#examples
        slack_response = app.client.search_messages(token=USER_TOKEN,
                                                    query='has::art-attention: -has::art-attention-resolved:',
                                                    cursor=next_cursor)
        messages = slack_response.get('messages', {})
        if messages:
            matches = messages.get('matches', [])
            all_matches.extend(matches)

        # https://api.slack.com/docs/pagination
        response_metadata = slack_response.get('response_metadata', {})
        next_cursor = response_metadata.get('next_cursor', None)

    all_matches = sorted(all_matches, key=lambda m: m.get('ts', '0.0'))

    if not all_matches:
        print('No messages matching attention emoji criteria')
        exit(0)

    print(json.dumps(all_matches))

    header_text = "Currently unresolved ART threads"
    fallback_text = header_text

    response_messages = []
    current_epoch_time = time.time()
    for match in all_matches:
        team_id = match.get('team', '')
        channel_id = match.get('channel', {}).get('id', '')
        channel_name = 'Unknown'
        if len(channel_id) > 0:
            conv_info = app.client.conversations_info(channel=channel_id)
            channel_name = conv_info.get('channel', {}).get('name_normalized', channel_name)
        text = match.get('text', 'Link')
        permalink = match.get('permalink', None)
        if not permalink:
            permalink = 'about:blank'
            text = json.dumps(match)

        fallback_text += f'\n{permalink}'
        timestamp = int(float(match.get('ts', '0.0')))
        str_date = datetime.datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

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
            f"*Channel:* <https://redhat-internal.slack.com/archives/{channel_id}|#{channel_name}>\n*Date:* {str_date}Z\n*Age:* {age} {age_type}\n*Message:* <{permalink}|Link>\n*Snippet:* {snippet}...")

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
    response = app.client.chat_postMessage(channel=TEAM_ART_CHANNEL,
                                           text=f'@{RELEASE_ARTIST_HANDLE} - {fallback_text}',
                                           blocks=header_block,
                                           unfurl_links=False)

    for response_message in response_messages:
        app.client.chat_postMessage(channel=TEAM_ART_CHANNEL,
                                    text=response_message,
                                    thread_ts=response['ts'])  # use the timestamp from the response
