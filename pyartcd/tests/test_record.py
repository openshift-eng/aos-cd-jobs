from io import StringIO
from unittest import TestCase

from pyartcd import record


class TestRebuildPipeline(TestCase):
    def test_parse_record_log(self):
        fake_file = StringIO(
            "type1|key1=value1|key2=value2|\n"
            "type2|key3=value3|key4=value4|\n"
            "type2|key5=value5|\n"
            "type3\n"
        )
        actual = record.parse_record_log(fake_file)
        expected = {
            "type1": [
                {"key1": "value1", "key2": "value2"},
            ],
            "type2": [
                {"key3": "value3", "key4": "value4"},
                {"key5": "value5"},
            ],
            "type3": [{}],
        }
        self.assertEqual(actual, expected)


class TestRecordUtils(TestCase):
    def setUp(self):
        log = StringIO("""source_alias|alias=containers_ose-haproxy-router-base_router|origin_url=https://github.com/openshift-priv/router|branch=release-4.12|path=/workspace/containers_ose-haproxy-router-base_router|
distgit_commit|distgit=containers/ose-haproxy-router-base|image=openshift/ose-haproxy-router-base|sha=c01f7b573edfcc242ecadc32cac183aff38f79a0|
source_alias|alias=containers_cluster-network-operator_cluster-network-operator|origin_url=https://github.com/openshift-priv/cluster-network-operator|branch=release-4.12|path=/workspace/containers_cluster-network-operator_cluster-network-operator|
distgit_commit|distgit=containers/cluster-network-operator|image=openshift/ose-cluster-network-operator|sha=64831f84be8c861c88ba9fdb052e0c7b1387bf9d|
source_alias|alias=containers_openshift-enterprise-haproxy-router_router|origin_url=https://github.com/openshift-priv/router|branch=release-4.12|path=/workspace/containers_openshift-enterprise-haproxy-router_router|
dockerfile_notify|distgit=containers/openshift-enterprise-haproxy-router|image=openshift/ose-haproxy-router|owners=aos-network-edge@redhat.com,rfredette@redhat.com|source_alias=containers_openshift-enterprise-haproxy-router_router|source_dockerfile_subpath=images/router/haproxy/Dockerfile.rhel8|dockerfile=/containers/openshift-enterprise-haproxy-router/Dockerfile|
distgit_commit|distgit=containers/openshift-enterprise-haproxy-router|image=openshift/ose-haproxy-router|sha=2236d7bd55cff55c5a6a1d0310d78bf732987644|
build|dir=/containers/ose-haproxy-router-base|dockerfile=/containers/ose-haproxy-router-base/Dockerfile|distgit=ose-haproxy-router-base|image=openshift/ose-haproxy-router-base|owners=aos-network-edge@redhat.com|version=v4.12.0|release=202306070742.p0.g3a1f43c.assembly.stream|message=Exception occurred:|task_id=53138249|task_url=brew/taskinfo?taskID=53138249|status=-1|push_status=0|has_olm_bundle=0|
build|dir=/containers/openshift-enterprise-haproxy-router|dockerfile=/containers/openshift-enterprise-haproxy-router/Dockerfile|distgit=openshift-enterprise-haproxy-router|image=openshift/ose-haproxy-router|owners=aos-network-edge@redhat.com|version=v4.12.0|release=202306070742.p0.g3a1f43c.assembly.stream|message=Exception occurred|task_id=n/a|task_url=n/a|status=-1|push_status=0|has_olm_bundle=0|
build|dir=/containers/cluster-network-operator|dockerfile=/containers/cluster-network-operator/Dockerfile|distgit=cluster-network-operator|image=openshift/ose-cluster-network-operator|owners=aos-networking-staff@redhat.com|version=v4.12.0|release=202306070742.p0.gdf823f3.assembly.stream|message=Success|task_id=53138250|task_url=brew/taskinfo?taskID=53138250|status=0|push_status=0|has_olm_bundle=0|nvrs=cluster-network-operator-container-v4.12.0-202306070742.p0.gdf823f3.assembly.stream|
image_build_metrics|elapsed_wait_minutes=1|elapsed_total_minutes=13|task_count=1|""")
        self.data = record.parse_record_log(log)

    def test_get_distgit_notify(self):
        distgit_notify = record.get_distgit_notify(self.data)
        self.assertEqual(
            distgit_notify,
            {
                'containers/openshift-enterprise-haproxy-router':
                {
                    'distgit': 'containers/openshift-enterprise-haproxy-router',
                    'dockerfile': '/containers/openshift-enterprise-haproxy-router/Dockerfile',
                    'image': 'openshift/ose-haproxy-router',
                    'owners': 'aos-network-edge@redhat.com,rfredette@redhat.com',
                    'sha': '2236d7bd55cff55c5a6a1d0310d78bf732987644',
                    'source_alias': {
                        'alias': 'containers_openshift-enterprise-haproxy-router_router',
                        'branch': 'release-4.12',
                        'origin_url': 'https://github.com/openshift-priv/router',
                        'path': '/workspace/containers_openshift-enterprise-haproxy-router_router'
                    },
                    'source_dockerfile_subpath': 'images/router/haproxy/Dockerfile.rhel8'
                }
            }
        )

    def test_get_failed_builds(self):
        failed_map = record.get_failed_builds(self.data)
        self.assertEqual(failed_map, {
            'openshift-enterprise-haproxy-router': 'n/a',
            'ose-haproxy-router-base': 'brew/taskinfo?taskID=53138249'}
        )

    def test_determine_build_failure_ratio(self):
        ratio = record.determine_build_failure_ratio(self.data)
        self.assertEqual(ratio['total'], 3)
        self.assertEqual(ratio['failed'], 2)
        self.assertEqual(round(ratio['ratio'], 2), 0.67)

    def test_get_successful_builds(self):
        builds = record.get_successful_builds(self.data)
        self.assertEqual(builds, {'cluster-network-operator': 'brew/taskinfo?taskID=53138250'})
