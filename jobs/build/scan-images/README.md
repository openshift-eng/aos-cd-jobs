This job pulls the images built by the `ose_images.sh` script and scans them
using `openscap` (via `atomic scan`).  If any CVEs are found, a notification
email is sent.
