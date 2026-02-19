---
trigger: always_on
---

When running commands on Windows, the run_command tool may append an extra quote or malform the command string, causing it to hang or fail.

To fix this, wrap the command in cmd /c and append & :: to the end. This executes the command and then executes a comment, which safely absorbs any trailing garbage characters.

Pattern:

cmd /c <your_command> & ::

Examples:

Instead of:

dir

Use:

cmd /c dir & ::

Instead of:

python main.py

Use:

cmd /c python [main.py](http://main.py) & ::