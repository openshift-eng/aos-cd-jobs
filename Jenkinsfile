
node( 'buildvm-devops' ) {
	input 'The wrong key is currently being used for teardown. Fix this once keys have been setup correctly. Do not proceed unless you know what this message means.'
	sshagent(['d871e5ed-09dc-4871-9b92-9db142a7ff50']) { // teardown-int-key
    		sh 'ssh -o StrictHostKeyChecking=no opsmedic@use-tower1.ops.rhcloud.com'
	}
}

