
de( 'buildvm-devops' ) {
	input 'The wrong key is currently being used for create. Fix this once keys have been setup correctly. Do not proceed unless you know what this message means.'
	sshagent(['3fc8b6ea-5188-45f3-a401-c28efd4887e4']) { // build-int-key
    		sh 'ssh -o StrictHostKeyChecking=no opsmedic@use-tower1.ops.rhcloud.comi delete'
	}
}

