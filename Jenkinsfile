
node( 'buildvm-devops' ) {
	sshagent(['423abbb6-72c1-4b23-a740-65118fa53ddb']) { // test_key cluster
    		sh 'echo About to ssh' 
    		sh 'ssh -o StrictHostKeyChecking=no opsmedic@use-tower1.ops.rhcloud.com uname -a'
	}
}

