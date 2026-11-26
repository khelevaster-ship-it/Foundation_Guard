# Dependencies and licences (checked 9 Nov 2026, AI-made, Claude)
FoundationGuard is released under the MIT licence (LICENSE).

- **In the Windows download only:** python.org's "embeddable" Python 3.12 for 64-bit Windows, unchanged, in its own
  `python\` folder with its own `LICENSE.txt` (Python Software Foundation licence; it also holds OpenSSL, SQLite,
  libffi, bzip2, XZ and Microsoft's C runtime files under their own licences, all listed in that file). The download
  is built with Inno Setup (its licence allows this use; none of its source is in this project). The repository
  itself ships none of these.
- **Bundled outside code in the repository:** none. Every file in fg/ and tests/ was written for this kit. No code was copied from other projects,
  answers sites or packages (checked: no copied or adapted blocks noted anywhere; all imports listed below).
- **Runs on:** Python 3 standard library only: argparse, datetime, fnmatch, glob, hashlib, json, os, platform, random, re, shlex,
  shutil, stat, subprocess, sys, textwrap, time, unittest, xml.etree.ElementTree (Python Software Foundation licence; nothing is shipped).
- **Optional:** pytest (MIT) runs the kit's own tests; git (GPL-2.0) is called as a separate program, not linked or shipped.
- **Data:** none bundled. The fresh test cases in the results were written by AI agents for these rounds; no outside datasets.
- **Not included:** any other project's code and art.
- **Name:** an unrelated GitHub project also called FoundationGuard (figma-cloud/FoundationGuard, about house foundations) exists.
