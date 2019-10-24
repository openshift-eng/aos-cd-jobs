This set of scripts helps you during an OCP4 branching event. It allows
you to promote builds from the previous 4.(x-1) candidate to the new
4.x candidate tag.

Steps:
1. Run `download-logs.sh` for the 4.(x-1) release. This will download all the image build
logs for the previous release.

2. Run `findit.sh` for the 4.(x-1) tags. This will search the previously downloaded
logs for uses of RPMs tagged into the candidate tag.

3. Evaluate results and run untag.sh to untag packages that are not being used.

4. Run tag-em.sh  which can tag builds from 4.(x-1) to 4.x. Run for
both rhel-7 and rhel-8 candidate tags.
   
5. Work with RCM on any reported errors.
