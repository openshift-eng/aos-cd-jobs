Allows root to allow network output to a set of CIDRs in addition to
all non EC2 AWS services. 
- The CIDRs should be included in one or more line delimited files.
- The AWS service CIDRs will be pulled dynamically from AWS.


```
# Prepare to only allow network output to this exact IP
[root@localhost buildvm-scripts]# echo 104.102.192.19/32 > approved_networks

# Install rules in NON-enforcing mode. This mode will cause disallowed
# outgoing connections to be made, but a LOG statement will be included
# in the journal.
[root@localhost buildvm-scripts]# ./canttouchthat.py -n approved_networks 
Removing all existing permanent rules
Adding rule for 104.102.192.19/32
Adding logging rule in ipv4 with prefix 'New Connection: '
Adding logging rule in ipv4 with prefix 'Disallowed Connection: '
Adding logging rule in ipv6 with prefix 'New Connection: '
Adding logging rule in ipv6 with prefix 'Disallowed Connection: '

# Ping a disallowed IP
[root@localhost buildvm-scripts]# ping -c 1 104.102.192.20
PING 104.102.192.20 (104.102.192.20) 56(84) bytes of data.
64 bytes from 104.102.192.20: icmp_seq=1 ttl=53 time=19.6 ms

--- 104.102.192.20 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms

# Check the logs to see the Disallowed entry
[root@localhost buildvm-scripts]# journalctl | grep 104.102.192.20
Sep 11 19:13:04 localhost.localdomain kernel: New Connection: IN= OUT=wlp4s0 SRC=192.168.187.204 DST=104.102.192.20 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=41741 DF PROTO=ICMP TYPE=8 CODE=0 ID=10677 SEQ=1 
Sep 11 19:13:04 localhost.localdomain kernel: Disallowed Connection: IN= OUT=wlp4s0 SRC=192.168.187.204 DST=104.102.192.20 LEN=84 TOS=0x00 PREC=0x00 TTL=64 ID=41741 DF PROTO=ICMP TYPE=8 CODE=0 ID=10677 SEQ=1

# You can remove the rules at any time
[root@localhost buildvm-scripts]# ./canttouchthat.py --clean

# Now let's turn on enforcement. Disallowed connections will be 
# logged and all packets dropped.
[root@localhost buildvm-scripts]# ./canttouchthat.py -n approved_networks --enforce
Removing all existing permanent rules
Adding rule for 104.102.192.19/32
Adding logging rule in ipv4 with prefix 'New Connection: '
Adding logging rule in ipv4 with prefix 'Disallowed Connection: '
Adding default DROP rule for ipv4
Adding logging rule in ipv6 with prefix 'New Connection: '
Adding logging rule in ipv6 with prefix 'Disallowed Connection: '
Adding default DROP rule for ipv6

# You can connect to the approved network
[root@localhost buildvm-scripts]# ping -c 1 104.102.192.19
PING 104.102.192.19 (104.102.192.19) 56(84) bytes of data.
64 bytes from 104.102.192.19: icmp_seq=1 ttl=53 time=19.8 ms

--- 104.102.192.19 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 19.824/19.824/19.824/0.000 ms

# But not anything else
[root@localhost buildvm-scripts]# ping -c 1 104.102.192.20
PING 104.102.192.20 (104.102.192.20) 56(84) bytes of data.
ping: sendmsg: Operation not permitted
^C
--- 104.102.192.20 ping statistics ---
1 packets transmitted, 0 received, 100% packet loss, time 0ms

# Remove the rules
[root@localhost buildvm-scripts]# ./canttouchthat.py --clean

# And the restrictions are gone
[root@localhost buildvm-scripts]# ping -c 1 104.102.192.20
PING 104.102.192.20 (104.102.192.20) 56(84) bytes of data.
64 bytes from 104.102.192.20: icmp_seq=1 ttl=53 time=17.9 ms

--- 104.102.192.20 ping statistics ---
1 packets transmitted, 1 received, 0% packet loss, time 0ms
rtt min/avg/max/mdev = 17.923/17.923/17.923/0.000 ms

```