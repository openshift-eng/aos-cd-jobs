ART synchronizes files for CI and QE to and S3 bucket art-srv-enterprise in the 
AWS account which hosts the ART OSD clusters (credentials in bitwarden for this
under "ART OSD Cluster AWS Account").

ART automation uses 'aws s3 sync' to put objects into the bucket. The credentials
used for this are attached to the bitwarden secret as a file (art-srv-enterperise.txt).

To read files, there is a CloudFront distribution setup to provide access to the 
otherwise private bucket content. The CloudFront is setup to only permit access
when a signed cookie is included in the request.

A signed cookie is a small payload saying what access is permitted and for how 
long, signed with a private key which was created for this purpose.

The application in this folder can create those signed cookies when provided
the cookie signing private key (stored as an attachment to the "ART OSD Cluster AWS Account"
item called: art-srv-enterprise-cookie-signing-private.key).  

The most important output of this program is the "flat" version of the cookie. The line
is populated in a secret that is included in a nginx configuration. The cookie value
will be included in proxied requests to S3 so that the caller does not need a secret. 

