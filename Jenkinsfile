
node( 'buildvm-devops' ) {
	input 'Are you certain you want to DELETE the cicd test cluster?'
	sshagent(['cicd']) {
    		sh 'ssh -o StrictHostKeyChecking=no opsmedic@use-tower1.ops.rhcloud.com delete'
	}
}

