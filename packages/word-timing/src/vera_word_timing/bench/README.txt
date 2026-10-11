VERA word-timing benchmark
==========================

What it does: installs VERA's local speech engines into this folder only,
transcribes and word-times a public-domain recording (LibriVox: the
Gettysburg Address), and records how fast it ran.

You need: a Mac (Apple Silicon preferred), internet, about 5 GB free disk
space and 20-40 minutes. No admin password. Nothing is installed outside
this folder.

1. Unzip vera-bench-kit.zip anywhere (e.g. Downloads).
2. Open Terminal, type `cd ` (with a space), drag the vera-bench-kit folder
   into the Terminal window, press Return.
3. Type `sh bench.sh` and press Return. Leave it running.
4. When it says "Done", send back the file bench-results.json.

To remove everything afterwards, delete the vera-bench-kit folder.
