import json
import boto3


def lambda_handler(event, context):
    response = event['Records'][0]['cf']['response']

    if int(response['status']) == 403:  # This is basically file-not-found from s3 if the user is authenticated
        request = event['Records'][0]['cf']['request']
        uri = request['uri']

        if uri.endswith('/') or uri.endswith('/index.html'):
            # Nothing to do. This should have already hit the index.html
            return response

        # Let's see if a s3 key prefix of this name exists
        bucket_name = 'art-srv-enterprise'
        s3 = boto3.resource('s3', region_name='us-east-1')
        s3_conn = boto3.client('s3')
        prefix = uri.lstrip('/')
        s3_result = s3_conn.list_objects_v2(Bucket=bucket_name, Prefix=prefix, Delimiter="/")

        if s3_result.get('CommonPrefixes', []) or s3_result.get('Contents', []):
            print(f'Redirecting because: {s3_result}')
            # If there are "sub-directories" or "files" in this directory, redirect with a trailing slash
            # So that the user will get a directory listing.
            host = request['headers']['host'][0]['value']
            # Otherwise, maybe the caller entered a directory name without
            # a trailing slash and it is not found. Make another attempt with a
            # trailing slash which should trigger the lookup of uri/index.html
            # if it exists.
            response['status'] = 302
            response['statusDescription'] = 'Found'
            response['body'] = ''
            response['headers']['location'] = [{'key': 'Location', 'value': f'{uri}/'}]

    return response
