
last_action_day = 0
year=getCurrentYear()

// TODO: as these fields mature and stop changing, change into be build parameters so that a simple script can trigger a build
config = input(
        message: 'Enter desired dates for cluster deployments (MM/DD/YYYYY)?\nDates are inclusive. Use 00/00/0000 if this step is not relevant to this run.',
        parameters: [
                [$class: 'hudson.model.StringParameterDefinition', defaultValue: '', description: 'Name of this sprint', name: 'sprint_name'],
                [$class: 'hudson.model.StringParameterDefinition', defaultValue: "00/00/${year}", description: 'Date for the teardown and recreate dev-preview-int (first Friday of the sprint)', name: 'int_recreate'],
                [$class: 'hudson.model.StringParameterDefinition', defaultValue: "00/00/${year}", description: 'Date of first upgrade for dev-preview-int (usually second Monday of the sprint)', name: 'int_upgrades_start'],
                [$class: 'hudson.model.StringParameterDefinition', defaultValue: "00/00/${year}", description: 'Date of last upgrade for dev-preview-int (usually third Monday of the sprint)', name: 'int_upgrades_stop'],
                [$class: 'hudson.model.StringParameterDefinition', defaultValue: "00/00/${year}", description: 'Date of first upgrade for dev-preview-stg (usually third Tuesday of the sprint)', name: 'stg_upgrades_start'],
                [$class: 'hudson.model.StringParameterDefinition', defaultValue: "00/00/${year}", description: 'Date of last upgrade for dev-preview-stg (usually third Friday of the sprint)', name: 'stg_upgrades_stop'],
                [$class: 'hudson.model.StringParameterDefinition', defaultValue: "00/00/${year}", description: 'Date of upgrade for dev-preview-prod (usually first Monday of \'next\' sprint); This process will not be performed without user input.', name: 'prod_upgrade'],
                [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'aos-devel@redhat.com, aos-qe@redhat.com', description: 'Success Mailing List', name: 'MAIL_LIST_SUCCESS'],
                [$class: 'hudson.model.StringParameterDefinition', defaultValue: 'jupierce@redhat.com,tdawson@redhat.com,smunilla@redhat.com,mwoodson@redhat.com,chmurphy@redhat.com', description: 'Failure Mailing List', name: 'MAIL_LIST_FAILURE'],
                [$class: 'BooleanParameterDefinition', defaultValue: false, description: 'Force immediate action (do not wait for disruption hour)?.', name: 'force'],
                [$class: 'BooleanParameterDefinition', defaultValue: false, description: 'Run in test mode?', name: 'test_mode'],
        ]
)

echo "Launching sprint ${config.sprint_name}"
echo "Configuration: ${config}"

// Make sure dates are valid
splitDate(config.int_recreate)
splitDate(config.int_upgrades_start)
splitDate(config.int_upgrades_stop)
splitDate(config.stg_upgrades_start)
splitDate(config.stg_upgrades_stop)
splitDate(config.prod_upgrade)
force = config.force

// Setting test_mode to true will emulate time moving by one hour every 30 seconds.
// Builds and deployments will not actually take place.
test_mode = config.test_mode

test_mode_date = getCurrentDateFields(false)

if ( test_mode ) {
    sshkey_dev_preview_int = "test-key"
    sshkey_dev_preview_stg = "test-key"
    sshkey_dev_preview_prod = "test-key"
} else {
    sshkey_dev_preview_int = "dev-preview-int"
    sshkey_dev_preview_stg = "test-key"
    sshkey_dev_preview_prod = "test-key"
}



while ( true ) {

    if ( !test_mode ) {
        echo "  Waiting 30 minutes before next check..."

        if ( !force ) {
            sleep( time: 30, unit: 'MINUTES' )
        }

    } else {
        echo "  RUNNING IN TEST MODE. 30 minute timeout is being bypassed and emulated clock is being increased by 1 hour. "
    }


    def todayFields = getCurrentDateFields(test_mode)

    if ( force ) {
        echo "    User has requested immediate action. Ignoring disruption window."
        force = false
    } else if ( todayFields[3] != 18 ) {
        echo "    It is not currently 18:00h. No deployments will be initiated."
        continue
    }


    phase = "dev-preview-int/create"
    if ( isToday( phase, todayFields, config.int_recreate ) ) {

        def rebuild = false
        while ( true ) {

            try {
                if ( rebuild ) {
                    stage( "${phase} openshift/ose build" ) {
                        runOSEBuild()
                    }
                }

                stage( "${phase} - Tearing down" ) {
                    runTowerOperation( sshkey_dev_preview_int, 'delete' )
                }

                stage( "${phase} - Provisioning and installing" ) {
                    runTowerOperation( sshkey_dev_preview_int, 'install' )
                }

                stage( "${phase} - Verify" ) {
                    //TODO: runTowerOperation( sshkey_dev_preview_int, 'verify' )
                }

                last_action_day = getDayOfYear()
                status_notify("dev-preview-int has been recreated", "Installed: https://console.dev-preview-int.openshift.com" )
                break
            } catch ( e ) {
                error_notify("${phase}", "${e}" )
                def response = input message: "Error: ${e}\\nRetry ${phase} or abort?", ok: 'Retry', parameters: [[$class: 'BooleanParameterDefinition', defaultValue: false, description: 'Force rebuild before retrying phase?.', name: 'rebuild']]
                rebuild = response.rebuild.toBoolean()
            }
        }
    }


    phase = "dev-preview-int/upgrades"
    if ( isTodayBetween( phase, todayFields, config.int_upgrades_start, config.int_upgrades_stop ) ) {

        def rebuild = false
        while ( true ) {

            try {
                if ( rebuild ) {
                    stage( "${phase} openshift/ose build" ) {
                        runOSEBuild()
                    }
                }

                stage( "${phase} - Upgrading" ) {
                    runTowerOperation( sshkey_dev_preview_int, 'upgrade' )
                }

                stage( "${phase} - Verify" ) {
                    //TODO: runTowerOperation( sshkey_dev_preview_int, 'verify' )
                }

                last_action_day = getDayOfYear()
                status_notify("dev-preview-int has been upgraded", "Upgraded: https://console.dev-preview-int.openshift.com" )
                break
            } catch ( e ) {
                error_notify("${phase}", "${e}" )
                def response = input message: "Error: ${e}\\nRetry ${phase} or abort?", ok: 'Retry', parameters: [[$class: 'BooleanParameterDefinition', defaultValue: false, description: 'Force rebuild before retrying phase?', name: 'rebuild']]
                rebuild = response.rebuild.toBoolean()
            }
        }

    }



    phase = "dev-preview-stg/upgrades"
    if ( isTodayBetween( phase, todayFields, config.stg_upgrades_start, config.stg_upgrades_stop ) ) {

        def rebuild = false
        while ( true ) {


            try {
                if ( rebuild ) {
                    stage( "${phase} openshift/ose build" ) {
                        runOSEBuild()
                    }
                }

                stage( "${phase} - Upgrading" ) {
                    runTowerOperation( sshkey_dev_preview_stg, 'upgrade' )
                }

                stage( "${phase} - Verify" ) {
                    //TODO: runTowerOperation( sshkey_dev_preview_stg, 'verify' )
                }

                last_action_day = getDayOfYear()
                status_notify("dev-preview-stg has been upgraded", "Upgraded: https://console.dev-preview-stg.openshift.com" )
                break
            } catch ( e ) {
                error_notify("${phase}", "${e}" )
                def response = input message: "Error: ${e}\nRetry ${phase} or abort?", ok: 'Retry', parameters: [[$class: 'BooleanParameterDefinition', defaultValue: false, description: 'Force rebuild before retrying phase?', name: 'rebuild']]
                rebuild = response.rebuild
            }
        }

    }


    phase = "dev-preview-prod/upgrade (PRODUCTION)"
    if ( isTodayOrBeyond( phase, todayFields, config.prod_upgrade ) ) {

        input "Continue only if you are ready to perform an upgrade on dev-preview-prod. The latest RPMs will be used (no new build will be performed)."

        while ( true ) {

            try {
                stage( "${phase} - Upgrading" ) {
                    runTowerOperation( sshkey_dev_preview_prod, 'upgrade' )
                }

                stage( "${phase} - Verify" ) {
                    //TODO: runTowerOperation( sshkey_dev_preview_prod, 'verify' )
                }

                status_notify("dev-preview-prod has been upgraded", "Upgraded: https://console.preview.openshift.com" )
                break
            } catch ( e ) {
                error_notify("${phase}", "${e}" )
                input message: "Error: ${e}\\nRetry ${phase} or abort?', ok: 'Retry"
            }
        }

        // TODO: Sprint over. Apparently successfully. Send email to QE?
        break  // Break out of master control loop
    }


}


def splitDate( date ) {
    def strings = date.split('/')
    if ( strings.length != 3 ) {
        error "Invalid date specified: ${date}"
    }
    def fields = [ strings[0].toInteger(), strings[1].toInteger(), strings[2].toInteger() ]
    if ( fields[2] > 0 && fields[2] < 2000 ) {
        error "Invalid year specified: ${date}"
    }
    if ( fields[1] > 31 ) {
        error "Invalid day specified: ${date}"
    }
    if ( fields[0] > 12 ) {
        error "Invalid day specified: ${date}"
    }
    return fields
}

def getCurrentDateFields( test_mode ) {
    Calendar c = Calendar.getInstance()
    def fields = [
            c.get(Calendar.MONTH)+1,
            c.get(Calendar.DAY_OF_MONTH),
            c.get(Calendar.YEAR),
            c.get(Calendar.HOUR_OF_DAY),
            c.get(Calendar.MINUTE),
            c.get(Calendar.DAY_OF_YEAR)
    ]
    if ( test_mode ) {
        test_mode_date[3]++
        if ( test_mode_date[3] == 24 ) {
            test_mode_date[3] = 0
            test_mode_date[1]++
            test_mode_date[5]++ // inc day of year
            if ( test_mode_date[1] == 32 ) {
                test_mode_date[1] = 1
                test_mode_date[0]++
                if ( test_mode_date[0] == 13 ) {
                    test_mode_date[0] = 1
                    test_mode_date[2]++
                }
            }
        }
        echo "Returning emulated time: ${fieldsToString(test_mode_date)}"
        return test_mode_date
    }
    return fields
}

def getCurrentYear() {
    return Calendar.getInstance().get(Calendar.YEAR)
}

def flattenDateToInt(fields) {
    return fields[2] * 100000 + fields[0] * 100 + fields[1]
}

def isToday( phase, currentDateFields, testDateString ) {
    echo "Checking whether ${fieldsToString(currentDateFields)} is equal to target date ${testDateString} as pre-requisite for phase: ${phase}"

    if ( last_action_day == getDayOfYear() ) { // prevent two actions on the same day
        echo "  Another phase has already been performed today; condition is not satisfied"
        return false
    }

    def testFields = splitDate(testDateString)
    if ( testFields[0] == 0 ) {
        echo "  Test date contained null month; condition is not satisfied"
        return false
    }
    return flattenDateToInt(currentDateFields) == flattenDateToInt(testFields)
}

def fieldsToString( dateFields ) {
    return "${dateFields[0]}/${dateFields[1]}/${dateFields[2]}(${dateFields[3]}:${dateFields[4]})"
}

def isTodayOrBeyond( phase, currentDateFields, testDateString ) {
    echo "Checking whether ${fieldsToString(currentDateFields)} is equal to or greater than target date ${testDateString} as pre-requisite for phase: ${phase}"
    def testFields = splitDate(testDateString)
    if ( testFields[0] == 0 ) {
        echo "  Test date contained null month; condition is not satisfied"
        return false
    }
    return flattenDateToInt(currentDateFields) >= flattenDateToInt(testFields)
}


def isTodayBetween( phase, currentDateFields, startDateString, stopDateString ) {
    echo "Checking whether ${fieldsToString(currentDateFields)} is equal-or-between dates ${startDateString}-${stopDateString} as pre-requisite for phase: ${phase}"

    if ( last_action_day == getDayOfYear() ) { // prevent two actions on the same day
        echo "  Another phase has already been performed today; condition is not satisfied"
        return false
    }

    def startFields = splitDate(startDateString)
    def stopFields = splitDate(stopDateString)
    if ( startFields[0] == 0 || stopFields[0] == 0 ) {
        echo "  Date range contained null month; condition is not satisfied"
        return false
    }

    // None of this silly math would be required if Jenkins whitelisted java.util.Date or all of Calendar
    return flattenDateToInt(currentDateFields) >= flattenDateToInt(startFields) && flattenDateToInt(currentDateFields) <= flattenDateToInt(stopFields)
}

def runTowerOperation( sshKeyId, operation ) {
    try {
        node() {
            sshagent([sshKeyId]) {
                sh "ssh -o StrictHostKeyChecking=no opsmedic@use-tower1.ops.rhcloud.com ${operation}"
            }
        }
    } catch ( err ) {
        error "Error running tower operation ${operation} on ${sshKeyId}: ${err}"
    }
}

def runOSEBuild() {
    try {
        if ( test_mode ) {
            echo "    ***Build would be triggered now if not in test mode***"
        } else {
            build job: '../aos-cd-builds/build%2Fose',
                parameters: [   [$class: 'StringParameterValue', name: 'OSE_MAJOR', value: '3'],
                                [$class: 'StringParameterValue', name: 'OSE_MINOR', value: '5'],
                            ]
        }
    } catch ( err ) {
        error "Error running openshift/ose build: ${err}"
    }
}

def getDayOfYear() {
    return getCurrentDateFields(test_mode)[5]
}

def status_notify(subject,msg) {
    echo "\n\n\nStaus: ${subject} ; Sending email:\n ${msg}\n\n\n"

    if ( test_mode ) {
        echo "    ***Email would have been sent if not in test mode***"
        return
    }

    mail(
            to: "${config.MAIL_LIST_SUCCESS}",
            from: "aos-cd@redhat.com",
            replyTo: 'jpierce@redhat.com',
            subject: "[aos-devel] [sprint-${config.sprint_name}] ${subject}",
            body: """\
${msg}

Jenkins job: ${env.BUILD_URL}
""");
}

def error_notify(subject,msg) {
    echo "\n\n\nError: ${subject} ; Sending email:\n ${msg}\n\n\n"

    if ( test_mode ) {
        echo "    ***Email would have been sent if not in test mode***"
        return
    }

    mail(
            to: "${config.MAIL_LIST_FAILURE}",
            from: "aos-cd@redhat.com",
            replyTo: 'jpierce@redhat.com',
            subject: "FAILURE [sprint-${config.sprint_name}] ${subject}",
            body: """\
${msg}

Jenkins job: ${env.BUILD_URL}

Job console: ${env.BUILD_URL}/console

Job input: ${env.BUILD_URL}/input
""");
}
