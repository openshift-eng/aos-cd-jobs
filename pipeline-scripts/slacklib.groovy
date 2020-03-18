import groovy.json.JsonOutput

/**
 * Example usage:
 *  checkout scm
 *  slacklib = load('pipeline-scripts/slacklib.groovy')
 *  slackChannel = slacklib.to('4.1')  // channel will be determined by major.minor
 *
 *  Best pattern:
 *    slackChannel.task("Releasing ${something}") {
 *        taskThread ->
 *        taskThread.say('progress...')
 *        taskThread.say('progress...')
 *        taskThread.say('progress...')
 *        error('Connection issue..')
 *    }  // Any exception will be caught, reported for the task, and rethrown
 *
 *  Non-closure based:
 *    jobThread = slackChannel.say('starting a thread for this job')
 *    jobThread.say('adding information to the thread')
 *    jobThread.say('another line')
 *    jobThread.failure('run images:rebase')
 *
 *  Custom channel:
 *    slackChannel = slacklib.to('#team-art') // channel identified explicitly
 *    slackChannel.say('Hi @art-team')
 */

// Maps builder emails to slack usernames IF email username does not match
email_to_slack_map = [
    'lmeyer@redhat.com': '@sosiouxme',
    'tbielawa@redhat.com': '@Tim Bielawa',
    'jdelft@redhat.com': '@joep',
    'shiywang@redhat.com': '@Shiyang Wang',
]

def getDefaultChannel() {
    return '#art-release'
}

def getBuildUser() {
    wrap([$class: 'BuildUser']) {
        if ( env.BUILD_USER_EMAIL ) { //null if triggered by timer
            return env.BUILD_USER_EMAIL
        } else {
            return 'Timer'
        }
    }
}

def getBuildURL() {
    return env.BUILD_URL
}

def getDisplayName() {
    return "${currentBuild.displayName}"
}

def notifySlack(channel, as_user, text, attachments=[], thread_ts=null, replyBroadcast=false, verbose=false) {
    // https://www.christopherrung.com/2017/05/04/slack-build-notifications/

    // If there is no thread already, announce job# and owner in the message
    if ( ! thread_ts ) {
        def owner = getBuildUser()
        if ( email_to_slack_map.get(owner, null) ) { // can we translate from email to slack handle?
            owner = email_to_slack_map[owner]
        } else if ( owner.indexOf('@') > -1 ) {
            owner = "@${owner.split('@')[0]}"  // use the email username as a slack handle
        }
        attachments << [
                title: "Job: ${env.JOB_NAME} <${getBuildURL()}console|${getDisplayName()}> by ${owner}",
                color: '#439FE0',
        ]
    }

    withCredentials([string(credentialsId: 'art-bot-slack-token', variable: 'SLACK_BOT_TOKEN')]) {

        base = [   channel: channel,
                   icon_emoji: ":robot_face:",
                   username: as_user,
                   attachments: attachments,
                   link_names: 1,
                   reply_broadcast: replyBroadcast,
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

        if ( verbose ) {
            echo "[SLACK]>>>\nRequest: ${payload}\nResponse: ${response}\n${response.content}\n<<<[SLACK]\n"
        }

         //print "Received slack response: ${response}\n\n"
         return readJSON(text: response.content)
    }
}

/**
 * @param channel_or_release An explicit channel name ('#art-team') or a string that contains a prefix of the
 *        release the jobs is associated with (e.g. '4.5.2-something' => '4.5'). If a release is specified, the
 *        slack channel will be #art-release-MAJOR-MINOR.
 *        If null or empty string, you can still call the object, but no output will be sent to slack
 * @param verbose Whether to print the entire slack request and response (optional).
 * @param as_user Slack handle to submit the message (optional).
 */
def to(channel_or_release, verbose=false, as_user='art-release-bot') {
    def channel = channel_or_release
    if ( channel && channel_or_release.charAt(0) != '#' ) {
        channel = getDefaultChannel()
        if ( channel_or_release.charAt(0).isDigit() ) { // something like 4.5?
            try {
                def parts = channel_or_release.split('\\D')  // split on any non-digit; '4.2.5' => ['4','2','5']
                if ( parts[0] == '3' || parts[0] == '4' ) {
                    // Turn into a release channel name: e.g. "4.1" -> "#art-release-4-1"
                    channel = "#art-release-${parts[0]}-${parts[1]}"
                } else {
                    echo "ERROR Unexpected fields in ${channel_or_release}"
                }
            } catch ( pe ) {
                echo "ERROR determining channel for ${channel_or_release}; using default ${getChannelDefault()}: ${pe}"
            }
        }
    }
    return new SlackOutputter(this, channel, as_user, null, [], verbose)
}

class SlackOutputter {
    private channel
    private script
    private thread_ts
    private as_user
    private pinnedAttachments // attachments which this SlackOutputter will always send
    private verbose

    public SlackOutputter(script, channel, as_user, thread_ts=null, pinnedAttachments=[], verbose=false) {
        this.script = script
        this.channel = channel
        this.as_user = as_user
        this.thread_ts = thread_ts
        this.pinnedAttachments = []
        this.verbose = verbose
    }

    /**
     * Pins an attachment so that output from this object (and objects it returns
     * from say() will always include the attachment.
     */
    public void pinAttachment(attachment) {
        this.pinnedAttachments << attachment
    }

    public void clearPinnedAttachments() {
        this.pinnedAttachments = []
    }

    public void setVerbose(b) {
        this.verbose = b
    }

    /**
     * Sends a message to the channel (and possibly slack thread) associated with this
     * SlackOutputter.
     * @param msg The text to send.
     * @param attachments An array of slack attachments (https://api.slack.com/messaging/composing/layouts#attachments)
     * @param replyBroadcast if within a thread and true, also send to main channel
     * @return Returns an SlackOutputter that will append to the thread associated with the message.
     */
    public say(msg, attachments=[], replyBroadcast=false) {
        def new_thread_ts = this.thread_ts
        if ( this.channel ) {
            def responseJson = script.notifySlack(this.channel, as_user, msg, attachments, this.thread_ts, replyBroadcast, this.verbose)
            if ( ! new_thread_ts ) {
                new_thread_ts = responseJson.message.ts
            }
        }
        return new SlackOutputter(this.script, this.channel, this.as_user, new_thread_ts, this.pinnedAttachments, this.verbose)
    }

    public failure(description, exception=null, attachments=[]) {
        attachments << [
                title: "Job: <${this.script.getBuildURL()}console|#${this.script.getDisplayName()}>",
                color: '#A12830',
        ]
        def msg = "Failure reported: ${description}"
        if ( exception ) {
            msg += " (Exception: ${exception})"
        }
        return this.say(msg, attachments, true)
    }

    public task(goal, closure) {
        def out = this
        try {
            if (!this.thread_ts) {
                out = this.say("Task: ${goal}")
            }
            closure(out)
        } catch ( goal_ex ) {
            out.failure( "Unable to: ${goal}", goal_ex )
            throw goal_ex
        }
    }

}

return this
