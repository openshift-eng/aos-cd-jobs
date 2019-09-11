This tool will idempotently apply a set of allowed CIDR ranges to the 
local network. Multiple input files can be specified. Each should contain
a line delimited CIDR entries.

``` bash
19:51 $ C1="172.217.7.238/32"
19:51 $ C2="172.217.15.100/32"

19:51 $ echo > n

19:51 $ sudo ./canttouchthat.py -n n --dry-run
There are presently 206 iptable rules installed
There are 0 OUTPUT rules under management

19:52 $ echo $C1 > n

19:52 $ sudo ./canttouchthat.py -n n --dry-run
There are presently 206 iptable rules installed
There are 0 OUTPUT rules under management
Would have ADDED rule: ['iptables', '-A', 'OUTPUT', '-d', '172.217.7.238/32', '-j', 'ACCEPT', '-m', 'comment', '--comment', 'Rule managed by ART']

19:52 $ sudo ./canttouchthat.py -n n 
There are presently 206 iptable rules installed
There are 0 OUTPUT rules under management
Adding rule for: 172.217.7.238/32

19:52 $ sudo ./canttouchthat.py -n n 
There are presently 207 iptable rules installed
There are 1 OUTPUT rules under management
Rule already present for 172.217.7.238/32

19:52 $ echo $C2 >> n

19:52 $ sudo ./canttouchthat.py -n n --dry-run
There are presently 207 iptable rules installed
There are 1 OUTPUT rules under management
Rule already present for 172.217.7.238/32
Would have ADDED rule: ['iptables', '-A', 'OUTPUT', '-d', '172.217.15.100/32', '-j', 'ACCEPT', '-m', 'comment', '--comment', 'Rule managed by ART']

19:52 $ sudo ./canttouchthat.py -n n
There are presently 207 iptable rules installed
There are 1 OUTPUT rules under management
Rule already present for 172.217.7.238/32
Adding rule for: 172.217.15.100/32

19:52 $ sudo ./canttouchthat.py -n n
There are presently 208 iptable rules installed
There are 2 OUTPUT rules under management
Rule already present for 172.217.7.238/32
Rule already present for 172.217.15.100/32

19:52 $ echo $C2 > n

19:53 $ sudo ./canttouchthat.py -n n --dry-run
There are presently 208 iptable rules installed
There are 2 OUTPUT rules under management
Rule already present for 172.217.15.100/32
Would have DELETED rule: ['iptables', '-D', 'OUTPUT', '-d', '172.217.7.238/32', '-j', 'ACCEPT', '-m', 'comment', '--comment', 'Rule managed by ART']

19:53 $ sudo ./canttouchthat.py -n n
There are presently 208 iptable rules installed
There are 2 OUTPUT rules under management
Rule already present for 172.217.15.100/32
Deleting rule for: 172.217.7.238/32

19:53 $ sudo ./canttouchthat.py -n n --dry-run
There are presently 207 iptable rules installed
There are 1 OUTPUT rules under management
Rule already present for 172.217.15.100/32

19:53 $ echo > n

19:53 $ sudo ./canttouchthat.py -n n --dry-run
There are presently 207 iptable rules installed
There are 1 OUTPUT rules under management
Would have DELETED rule: ['iptables', '-D', 'OUTPUT', '-d', '172.217.15.100/32', '-j', 'ACCEPT', '-m', 'comment', '--comment', 'Rule managed by ART']

19:53 $ sudo ./canttouchthat.py -n n
There are presently 207 iptable rules installed
There are 1 OUTPUT rules under management
Deleting rule for: 172.217.15.100/32

19:53 $ sudo ./canttouchthat.py -n n
There are presently 206 iptable rules installed
There are 0 OUTPUT rules under management

19:53 $ sudo ./canttouchthat.py -n n
[sudo] password for jupierce: 
There are presently 206 iptable rules installed
There are 0 OUTPUT rules under management
```

