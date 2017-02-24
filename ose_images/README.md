ose_images.sh is a script initially designed for making image builds semi-automated.
It has grown beyond that, but that is still the heart of the program.

ose_images.sh - Can be run from anywhere, usually in /usr/bin/
ose.conf - Need to be the same directory as ose_images.sh or in /etc/

Because ose.conf can be in the same directory as ose_images.sh, if you don't have 
root access to a machine (for etc or /usr/bin) you can still run it.

For image pushes, you need to either be able to run docker pushes as your user,
or run the script in sudo mode.
