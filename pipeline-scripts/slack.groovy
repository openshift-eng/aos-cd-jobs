import groovy.json.JsonOutput

def notifySlack(channel, text, attachments=[], thread_ts=null) {
    // https://www.christopherrung.com/2017/05/04/slack-build-notifications/

     withCredentials([string(credentialsId: 'slack_token_crel-bot', variable: 'SLACK_BOT_TOKEN')]) {

        base = [   channel: channel,
                   icon_emoji: ":robot_face:",
                   username: "crel-bot",
                   attachments: attachments,
                   link_names: 1,
                   // icon_url
        ]

        if ( text ) {
            base['text'] = text
        }

        if ( thread_ts ) {
            base['thread_ts'] = thread_ts
        }

        def payload = JsonOutput.toJson(base)
        // echo "Sending slack notification: ${payload}\n"
        response = httpRequest(
                        // consoleLogResponseBody: true, // Great for debug, but noisy otherwise
                        httpMode: 'POST',
                        quiet: true,
                        contentType: 'APPLICATION_JSON',
                        customHeaders: [
                            [   maskValue: true,
                                name: 'Authorization',
                                value: "Bearer $SLACK_BOT_TOKEN"
                            ]
                        ],
                        ignoreSslErrors: true,
                        requestBody: "${payload}",
                        url: 'https://slack.com/api/chat.postMessage'
        )

         //print "Received slack response: ${response}\n\n"
         return readJSON(text: response.content)
    }
}

def newSlackThread(channel, text, attachments=[]) {
    json = notifySlack(channel, text, attachments)
    return json.message.ts
}

// Default channel for crel slack notifications
crel_channel = '#crel-notifications'

def crel_slack_thread_channel(channel) {
    crel_channel = channel
}

// Global notification attachments for slack notifications.
crel_notification_attachments = []

crel_current_thread_ts = null

def crel_slack_notification(text, additional_attachments = [], with_callouts=false, thread_ts=null) {
    try {
        if (with_callouts) {
            attachments = additional_attachments + crel_notification_attachments
        } else {
            attachments = additional_attachments
        }
        slack_lib.notifySlack(crel_channel, text, attachments, thread_ts)
    } catch ( e ) {
        echo "Error sending slack notification: ${e}"
    }
}

def crel_slack_thread_append(text, additional_attachments=[], with_callouts=false) {
    crel_slack_notification(text, additional_attachments, with_callouts, crel_current_thread_ts)
}

def crel_slack_thread(title, color='#439FE0', attachments=[]) {
    attachments << [
            title: "${title}\nJob: <${env.BUILD_URL}console|#${currentBuild.number}> by ${BUILDER_EMAIL}  -- <https://github.com/openshift/continuous-release-jobs/blob/master/docs/openshift-cr-jenkins-access.md|Can't access Jenkins?>",
            color: color,
    ]
    crel_current_thread_ts = slack_lib.newSlackThread(crel_channel, null, attachments)
}

return this