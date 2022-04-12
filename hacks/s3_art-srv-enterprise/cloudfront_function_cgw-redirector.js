/*
 * A viewer request function that will alter the incoming request URI and make it 
 * appropriate for the CGW server (which does not have arch specific directories).
 * This must manually be updated in ART's CloudFront if it is changed.
 */
function handler(event) {
    var request = event.request;
    
    var prefix = '/pub/openshift-v4/x86_64/clients/'
    if (request.uri.startsWith(prefix)) {
        // eliminate the x86_64/ to be consistent with CGW directory structure
        request.uri = '/pub/openshift-v4/clients/' + request.uri.substring(prefix.length);
    }

    var prefix2 = '/pub/openshift-v4/amd64/clients/'
    if (request.uri.startsWith(prefix2)) {
        // eliminate the x86_64/ to be consistent with CGW directory structure
        request.uri = '/pub/openshift-v4/clients/' + request.uri.substring(prefix2.length);
    }
    
   return request;
}
