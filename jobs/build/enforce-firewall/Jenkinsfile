node {
    properties(
        [
            buildDiscarder(
                logRotator(
                    artifactDaysToKeepStr: '',
                    artifactNumToKeepStr: '',
                    daysToKeepStr: '',
                    numToKeepStr: '360'
                )
            ),
            [
                $class : 'ParametersDefinitionProperty',
                parameterDefinitions: [
                    [
                        name: 'MOCK',
                        description: 'Mock run to pickup new Jenkins parameters?',
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: false,
                    ],
                ],
                parameterDefinitions: [
                    [
                        name: 'DRY_RUN',
                        description: "Don't change anything, just detect the current enforcement state",
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: false,
                    ],
                ],
                parameterDefinitions: [
                    [
                        name: 'NO_SLACK',
                        description: "Don't send a notification over slack if the rules had to be reapplied",
                        $class: 'hudson.model.BooleanParameterDefinition',
                        defaultValue: false,
                    ],
                ]

            ],
            disableResume(),
            disableConcurrentBuilds()
        ]
    )
    checkout scm
    def buildlib = load( "pipeline-scripts/buildlib.groovy" )
    def commonlib = buildlib.commonlib
    def slacklib = commonlib.slacklib
    commonlib.describeJob("enforce-firewall", """
        <h2>Automatically re-enables the firewall</h2>
        <b>Timing</b>: The scheduled job of the same name runs this twice daily.

        Checks if the firewall rules are enforcing. If they are not
        then they will be reapplied. If the rules are reapplied by
        this job then a notification will be sent over slack to the
        <code>#team-art</code> channel.

        Job supports a few parameters:

        <ul>
          <li><b>DRY_RUN</b> - Only <b>check</b> if the rules are presently enforcing</li>
          <li><b>NO_SLACK</b> - Don't send enforcement notifications out over slack</li>
        </ul>
    """)
    needApplied = false
    reapplied = false
    notifyChannel = '#art-bot-test'

    // ######################################################################
    // Check if the firewall rules are presently enforcing. If they
    // are enforcing then we should not be able to query random hosts
    // not on the allowed list.
    def extAccess = httpRequest(responseHandle: 'NONE',
				url: 'https://www.yahoo.com',
				timeout: 15)
    if ( extAccess.response == '200' ) {
	needApplied = true
	echo "need to turn on the firewall"
	reapplied = true
    }


    // ######################################################################
    // Notify art team if the rules had to be reapplied AND NO_SLACK is false
    if ( !params.NO_SLACK && reapplied ) {
        slackChannel = slacklib.to(notifyChannel)
        slackChannel.say('Hi @tbielawa')
    }

}
