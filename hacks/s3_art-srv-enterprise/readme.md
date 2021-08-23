mirror.openshift.com is a host which provides public access to an array of artifacts to customers. It differs from the customer portal in that it does not require authentication to download content.

The legacy infrastructure run by Service Delivery is to be [decommissioned EOY 2021](https://source.redhat.com/groups/public/openshiftplatformsre/blog/mirroropenshiftcom_end_of_life_announcement).

The current direction for replacing this infrastructure is an AWS S3 bucket behind CloudFront.

CloudFront provides worldwide distribution, but it is not a drop in replacement.
- 
- Provide an Apache-style file listing for directory structures within that S3 bucket (S3 content is not even technically organized by directories). 

### /enterprise authentication
CloudFront does not support client certificate based authentication (used by mirror.openshift.com/enterprise today). Client certificate based auth could have been preserved with a small deployment (e.g. of nginx) to proxy requests, but this introduced an unnecessary bottleneck and would have created an operations concern for the ART team.

Instead, the new infrastructure will be secured with basic auth (username & password) for authentication. This is enforced by a CloudFront function setup as a View Request hook. The View Request checks basic authentication whenever a /enterprise path is requested. See lambda_art-srv-request-basic-auth.js, but note that the username/password has been removed from the code. 


### /pub directory listing
CloudFront does not provide an Apache-style file listing for directory structures within that S3 bucket (S3 content is not even technically organized by directories). The current https://mirror.openshift.com/pub does provide listings, so it was necessary to add something novel to the CloudFront distribution.

The solution has different aspects:
1. The View Request CloudFront function will detect if the user is requesting a path terminating in '/' (i.e. a likely directory listing) and modify the request in-flight to request /index.html with the same path.
2. A CloudFront behavior is setup to handle requests to *.index.html. An Origin Request Lambda@Edge function is setup to handle those requests (see lambda_art-srv-enterprise-s3-get-index-html-gen.py). It queries S3 and formulates an index.html dynamically and sends it back to the client. 
3. An Origin Response method is setup for the '*' behavior. It detects 403 (permission denied - which indicates the file was not found in S3) and determines whether to redirect the client to a directory listing (i.e. the path requested plus '/'). This catch ensures that customers typing in a directory name with out a trailing slash will get redirected to a directory listing index of a file-not-found (see lambda_art-srv-enterprise-s3-redirect-base-to-index-html.py).  



 
