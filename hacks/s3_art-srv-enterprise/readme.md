mirror.openshift.com is a host which provides public access to an array of artifacts to customers. It differs from the customer portal in that it does not require authentication to download content.

The legacy infrastructure run by Service Delivery is to be [decommissioned EOY 2021](https://source.redhat.com/groups/public/openshiftplatformsre/blog/mirroropenshiftcom_end_of_life_announcement).

The current direction for replacing this infrastructure is an AWS S3 bucket behind CloudFront.

CloudFront provides worldwide distribution, but it is not a drop in replacement. It did not:
- Provide an Apache-style file listing for directory structures within that S3 bucket (S3 content is not even technically organized by directories). 
- Provide for client certificate authentication like the legacy mirror.openshift.com/enterprise. 

### /enterprise authentication
CloudFront does not support client certificate based authentication (used by the legacy mirror.openshift.com/enterprise). Client certificate based auth could have been preserved with a small deployment (e.g. of nginx) to proxy requests, but this introduced an unnecessary bottleneck and would have created a new operational concern for the ART team.

Instead, the new infrastructure will be secured with basic auth (username & password) for authentication. This is enforced by a CloudFront function setup as a View Request hook. The View Request checks basic authentication whenever a /enterprise path is requested. See cloudfront_function_art-srv-request-basic-auth.js, but note that the username/password has been removed from the code. 


### /pub directory listing
CloudFront does not provide an Apache-style file listing for directory structures within that S3 bucket (S3 content is not even technically organized by directories). The current https://mirror.openshift.com/pub does provide listings, so it was necessary to add something novel to the CloudFront distribution.

The solution has different aspects:
1. The View Request CloudFront function will detect if the user is requesting a path terminating in '/' (i.e. a likely directory listing) and modify the request in-flight to request /index.html with the same path.
2. A CloudFront behavior is setup to handle requests to *.index.html. An Origin Request Lambda@Edge function is setup to handle those requests (see lambda_art-srv-enterprise-s3-get-index-html-gen.py). It queries S3 and formulates an index.html dynamically and sends it back to the client. 
3. An Origin Response method is setup for the '*' behavior. It detects 403 (permission denied - which indicates the file was not found in S3) and determines whether to redirect the client to a directory listing (i.e. the path requested plus '/'). This catch ensures that customers typing in a directory name with out a trailing slash will get redirected to a directory listing index of a file-not-found (see lambda_art-srv-enterprise-s3-redirect-base-to-index-html.py).  

#### Legacy single-arch locations
Directories like `/pub/openshift-v4/clients` and `/pub/openshift-v4/dependencies` are a legacy location for x86_64 artifacts. On the original mirror.openshift.com, these directories were updated to be symlinks to arch qualified directories like `/pub/openshift-v4/x86_64/clients`.  Since there are no symlinks in S3, the redirection on the new mirror is performed by intercepting and altering the URI in incoming requests (hacks/s3_art-srv-enterprise/cloudfront_function_art-srv-request-basic-auth.js).

This is critical to understand because, even if s3 content is pushed under /pub/openshift-v4/clients, no user going through cloudfront is going to be able to see it.

#### Proxying to Red Hat Content Gateway (CGW)
Some teams that traditionally had ART publishing their clients to mirror.openshift.com have opted to host their content on Red Hat's content gateway (CGW). However, those teams still need older URLs to resolve. As such, certain directories on the new mirror.openshift.com are designed to proxy content from CGW.

This was achieved by adding the CGW domain as an origin for our cloudfront distribution. This allows us to, for example, proxy a request to cloudfront for /pub/openshift-v4/clients/crc to pull content from https://developers.redhat.com/content-gateway/rest/mirror/pub/openshift-v4/clients/crc/ . This is another case where even if content is written to our s3 bucket, it will not be visible to users of cloudfront.

### Generating credentials
See gen_password.py. 

### Backup and restore
The art-srv-enterprise bucket has S3 versioning enabled. This means that deleted files can be restored if it is done quickly. There is a lifecycle rule that will permanently delete these files after 30 days.

 
