buildlib = load("pipeline-scripts/buildlib.groovy")
commonlib = buildlib.commonlib
workdir = "crc"
sourceDomain = "cdk-builds.usersys.redhat.com"
releaseVer = ''

def initialize() {
    buildlib.cleanWorkdir(workdir)
    if ( !params.RELEASE_URL.contains(sourceDomain) ) {
	error("RELEASE_URL is not the expected host: ${sourceDomain}")
    }

    releaseVer = params.RELEASE_URL.split('/')[-1]
    currentBuild.displayName += "${params.DRY_RUN ? '[NOOP]' : ''} ${releaseVer}"
}

// Download the release directory contents. 'wget' will place the
// results into a directory matching the hostname in
// params.RELEASE_URL
def crcDownloadRelease() {
    // -r           => Recursive
    // --level=1    => Do not descend or walk away
    // --no-parent  => Do not download higher directories
    // --cut-dirs=4 => Don't make the 4 extra parent directories on the file system
    def cmd = "wget -r --level=1 --no-parent --cut-dirs=4 ${params.RELEASE_URL}"
    dir ( workdir ) {
	def result = commonlib.shell(script: cmd)
	// Rename it from the domain name to the actual version
	commonlib.shell(script: "mv ${sourceDomain} ${releaseVer}")
	// And update 'latest' symlink, of course
	commonlib.shell(script: "ln -s ${releaseVer} latest")
    }
}

// Maybe rsync this stuff to the use-mirror staging ground. Noop mode
// will just show you what would have been synced.
def crcRsyncRelease() {
    def dest = "use-mirror-upload.ops.rhcloud.com:/srv/pub/openshift-v4/clients/crc"
    def dry = params.DRY_RUN ? '--dry-run' : ''
    // The --exclude's remove the commonlib.shell directory files and
    // the index.html files from the files to be transferred
    cmd = "rsync ${dry} -av --delete-after --exclude='shell' --exclude='index*' --progress --no-g --omit-dir-times --chmod=Dug=rwX -e 'ssh -l jenkins_aos_cd_bot -o StrictHostKeyChecking=no' ${workdir}/${releaseVer} ${workdir}/latest ${dest}/"
    commonlib.shell(
	script: cmd,
	returnAll: true
    )
}

def crcPushPub() {
    if ( params.DRY_RUN ) {
	echo("[DRY-RUN] Would have ran 'push.pub.sh openshift-v4 -v' on use-mirror-upload")
    } else {
	echo("Running 'push.pub.sh openshift-v4 -v' on use-mirror-upload. This might take a little while.")
	mirror_result = buildlib.invoke_on_use_mirror("push.pub.sh", "openshift-v4", '-v')
	if (mirror_result.contains("[FAILURE]")) {
	    echo(mirror_result)
	    error("Error running signed artifact sync push.pub.sh:\n${mirror_result}")
	}
    }
}

return this
