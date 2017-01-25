node( 'buildvm-devops' ) {
	docker.image('maven:3.3.3-jdk-8').inside('--privileged') {
		sh 'mvn -version'
		writeFile( file:'test.txt', text:'hello' ) 
	}
	sh 'ls -l'
}
