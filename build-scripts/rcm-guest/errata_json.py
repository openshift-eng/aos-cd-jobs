#!/usr/bin/python -tt

import os
import collections
import urllib

try:
    import simplejson
except ImportError:
    import json as simplejson

from kobo.shortcuts import run


# Constants
ET_SERVER = 'https://errata.devel.redhat.com'
#ET_SERVER = 'https://errata-devel.app.eng.bos.redhat.com'
#ET_SERVER = 'https://errata-stage.app.eng.bos.redhat.com/'
DEBUG = False
AUTH_USER = None
USER_AGENT = 'rcm-errata (curl)'

class ErrataToolError(Exception):
    pass

def _curl(url, method='GET', content='application/json', output='application/json', data=None):
    cmd = ['curl',
           '-X', method,
           '-H', 'Accept: %s' % output,
           '-k',
           '-A', USER_AGENT,
           '-s']

    if AUTH_USER:
        # unusual case, perhaps a development/testing server.
        # Note: curl wipes out the -u argument from the process table so it's not _too_
        # insecure...
        cmd += ['--anyauth', '-u', AUTH_USER]
    else:
        # typical case, authenticating by kerberos
        cmd += ['--negotiate', '-u', ':']

    data_file = None
    if data:
        # If there is data to send in the request, put it in a file to avoid hitting
        # arg length limits
        data_file = pack_data(data)
        cmd += ['-H', 'Content-Type: %s' % content,
                '-d', '@' + data_file]
    elif method in ['POST', 'PUT', 'PATCH']:
        # Explicitly tell curl that we have no data; otherwise it will not set
        # a Content-Length header, which breaks on some servers
        cmd += ['-d', '']

    # attempt the command
    try:
        if DEBUG:
            print 'Attempting URL: %s' % url
            print 'full command: %s' % cmd
        cmd += [url]
        rv, output = run(cmd, can_fail=True)
        if DEBUG and output: print 'OUTPUT:\n', output
    finally:
        if data_file:
            # Make sure to remove the tempory data file once curl is complete
            try: os.unlink(data_file)
            except: print "Warning: could not delete %s" %data_file


    # Handle exceptions
    if rv:
        raise ErrataToolError("failed: %s" % rv)
    if '401 Authorization Required' in output:
        raise ErrataToolError('Could not authenticate with ET. kinit?')
    # output can be empty, for example, a successful update (PUT method) to an
    # advisory will return no advisory information
    if not output.strip():
        return "{}"
    einfo = simplejson.loads(output.replace('\n', ''))
    if 'error' in einfo and einfo['error'] != '':
        raise ErrataToolError("API Error: %s" %einfo['error'])
    if 'errors' in einfo and len(einfo['errors']):
        raise ErrataToolError("API Errors: %s" %str(einfo['errors']))

    return output

def convert_release(release):
    r = release.replace('.', '_')
    r = r.replace('-', '_')
    return r.replace(' ', '%20').lower()

def pack_data(data):
    output_file = '/tmp/errata_data%s.json' %os.getpid()
    with open(output_file, 'w') as fp:
        fp.write(simplejson.dumps(data))
    return output_file

# GET METHODS
def get_json(url, data=None):
    """Return a json string at a URL provided by the Errata Tool"""
    if data:
        return simplejson.loads(_curl(url, data=data))
    return simplejson.loads(_curl(url))

def get_release_url(release):
    return ('%s/errata/errata_for_release/%s.json' % \
            (ET_SERVER, convert_release(release)))

def get_release(release, field='all'):
    """return a list of advisories filed under a specific release"""
    advisories = get_json(get_release_url(release))
    if type(advisories) == dict and advisories.has_key('error'):
        raise ErrataToolError(advisories['error'])
    if field == 'all':
        return advisories
    else:
        return [a[field] for a in advisories]

def get_releases():
    return get_json("%s/api/v1/releases" % ET_SERVER)

def get_release_details_by_id(release_id):
    """
    Get the details of a release by its id.
    """
    return get_json("%s/api/v1/releases/%s" % (ET_SERVER, release_id))

def get_release_ids_by_name(release_name):
    """
    Get the release IDs by release name.
    """
    releases = get_json('%s/api/v1/releases' % ET_SERVER, \
                       data={'filter': {'name': release_name}})
    return [r['id'] for r in releases['data']]

def is_batch_enabled(release_id):
    """
    Check whether batching is enabled for a release.
    """
    details = get_release_details_by_id(release_id)
    return details['data']['attributes']['enable_batching']

def get_batch_by_release_id(release_id):
    """
    Get batch details by release id.
    """
    filter = {'filter': {'release': {'id': release_id}}}
    return get_json('%s/api/v1/batches' % ET_SERVER, data=filter)

def get_release_for_advisory(eid):
    """return the Errata Release of a given advisory"""
    edetails = get_json('%s/api/v1/erratum/%s.json' % (ET_SERVER, eid))
    etype = edetails['errata'].keys()[0]  # ET sucks sometimes
    rid = edetails['errata'][etype]['group_id']
    return get_json('%s/release/show/%s.json' % (ET_SERVER, rid))

def get_builds(id):
    """return build details about an advisory"""
    return get_json('%s/brew/list_files/%s.json' % (ET_SERVER, id))

def get_multimappings():
    """return multi-product mappings"""
    return get_json('%s/multi_product_mappings' % ET_SERVER)

def get_paginated(url, data, page_size=200):
    """Get all pages from a paginated API"""
    data = data.copy()
    page_number = 1
    data['page'] = {'number': page_number,
                    'size':   page_size}

    out = []
    while True:
        data['page']['number'] = page_number
        this_page = simplejson.loads(_curl(url, data=data))

        out += this_page

        # Keep going until we know we're on the last page
        if len(this_page) < page_size:
            return out

        page_number += 1

def get_batches(active_only=True):
    """
    Get details of all batches ordered by name.

    Returns an array of advisory batches under the top-level key 'data'.
    """
    filter = {}
    if active_only:
        filter = {"filter": {"is_active": active_only}}
    return get_json('%s/api/v1/batches.json' % (ET_SERVER), data=filter)

def get_batch(id):
    """
    Get the details of a batch by its id.

    Parameters are returned under the top-level key data which is further
    divided into attributes.
    """
    return get_json('%s/api/v1/batches/%s.json' % (ET_SERVER, id))

def get_batches_for_release(release_id, active_only=True):
    """
    Get the batches for a release.

    Return the list of batch's ID.
    """
    batches = []
    all_batches = get_batches(active_only)['data']
    for batch in all_batches:
        if batch['relationships']['release']['id'] == release_id:
            batches.append(batch['id'])
    return batches

def get_advisory(id):
    """
    Get the details of an advisory by its id.
    """
    return get_json('%s/api/v1/erratum/%s' % (ET_SERVER, id))

def get_push(crit):
    """
    Get push jobs matching given criteria.
    """
    url = '%s/api/v1/push' % (ET_SERVER)
    data = {'filter': crit}
    return get_paginated(url, data)

# PUT METHODS
def set_doc_approval(id):
    return _curl('%s/api/v1/erratum/%d' % (ET_SERVER, id),
        method='PUT',
        data={'advisory': {'doc_complete': 1}})

def close_advisory(id):
    return _curl('%s/api/v1/erratum/%d' % (ET_SERVER, id),
        method='PUT',
        data={'advisory': {'closed': 1}})

def set_text_only_location(id, ltype, label):
    """
    Enables channels/repos to receive a text-only notification.
    ltype - the type of location are you setting, it is either repo or channel
    label - this is a value you would see beside a checkbox when you click the
    "Set" button.
    """
    if ltype not in ('repo', 'channel'):
        raise ErrataToolError('invalid ltype!')
    return _curl(
        '%s/api/v1/erratum/%d/text_only_%ss' % (ET_SERVER, id, ltype),
        method='PUT',
        data=[{'enabled': True, ltype: label}])

# POST METHODS
def refresh_bugs(bugs):
    """
    Refresh a single or list of bugs
    """
    if type(bugs) != list:
        bugs = [bugs]
    return _curl(
        '%s/api/v1/bug/refresh' % (ET_SERVER),
        method='POST',
        data=bugs)

def change_state(id, state):
    """change an advisory state to $state"""
    return _curl(
        '%s/api/v1/erratum/%s/change_state' % (ET_SERVER, id),
        method='POST',
        data={'new_state': state})

def add_builds(id, pv, package, ptype):
    """Adds a brew package to an advisory, in nvr format"""
    return _curl(
        '%s/api/v1/erratum/%s/add_builds' % (ET_SERVER, id),
        method='POST',
        data = [{
            'product_version'  : pv,
            'build'   : package,
            'file_types'   : ptype,
        }])

def add_build(id, pv, package):
    """Adds a brew package to an advisory, in nvr format"""
    return _curl(
        '%s/api/v1/erratum/%s/add_build' % (ET_SERVER, id),
        method='POST',
        data = {
            'product_version'  : pv,
            'nvr'   : package,
        })

def remove_build(id, package):
    """Remove a brew package from an advisory, in nvr format"""
    return _curl(
        '%s/api/v1/erratum/%s/remove_build' % (ET_SERVER, id),
        method='POST',
        data={'nvr': package})

def push_advisory(id, target):
    """
    Push an advisory to a target. Examples are: 'stage', 'rhn_live', or 'cdn'
    """
    # XXX: need a wait flag, see bz1134514 for an example
    url = '%s/api/v1/erratum/%d/push' % (ET_SERVER, id)
    data = None
    if target not in ('stage', 'rhn_live', 'cdn'):
        raise ErrataToolError('unknown target!')
    if target == 'stage':
        url +='?defaults=stage'
    else:
        data = [{'target': target}]
    return _curl(url, method='POST', data=data)

def build_query_string(data):
    query = {}

    for (k, v) in data.iteritems():
        query_key = k
        if isinstance(v, collections.Sequence) and not isinstance(v, basestring):
            query_key += '[]'
        query[query_key] = v

    return urllib.urlencode(query, doseq=True)

def push_multi_advisory(crit, targets, dryrun=False):
    """
    Push errata matching given criteria to a target.
    """
    url = '%s/api/v1/push' % (ET_SERVER)
    query = {}

    for (k, v) in crit.iteritems():
        query['filter[%s]' % k] = v

    data = None

    if targets == 'stage':
        query['defaults'] = 'stage'
    elif targets == 'live':
        query['defaults'] = 'live'
    else:
        data = targets

    if dryrun:
        query['dryrun'] = 1

    query_str = build_query_string(query)
    if query_str:
        url += '?' + query_str

    return simplejson.loads(_curl(url, method='POST', data=data))

def new_advisory(etype, impact, product, release, solution, desc, email,
                 owner, synopsis, topic, bugs, other=dict()):
    # convert the bugs to a string if we receive a list of bugs
    if type(bugs) == list:
        bugs = ' '.join(bugs)

    # These fields are all REQUIRED by the ET API. For details see:
    # https://engineering.redhat.com/docs/en-US/Application_Guide/80.Developer/html/Errata_Tool/api-http-api.html#api-apis
    advisory = { 
        'errata_type'           : etype,
        'security_impact'       : impact,
        'solution'              : solution,
        'description'           : desc[:4000], # rhn limitation
        'manager_email'         : email,
        'package_owner_email'   : owner,
        'synopsis'              : synopsis,
        'topic'                 : topic,
        'idsfixed'              : bugs,
    }
    data = {
        'advisory'  : dict(advisory.items() + other.items()),
        'product'   : product,
        'release'   : release,
    }
    return _curl('%s/api/v1/erratum' % ET_SERVER, method='POST', data=data)

if __name__ == '__main__':
    print 'This is a library.'

