import yum
import sys

yb = yum.YumBase()
yb.conf.disable_excludes = ["all"]
pkgs = yb.doPackageLists('available', patterns=[sys.argv[1]], showdups=True).available
pkgs.sort(key=lambda x: x.version)
for p in pkgs:
    print p.vra
