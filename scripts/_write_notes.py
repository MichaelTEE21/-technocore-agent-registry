import sys
from pathlib import Path
Path(sys.argv[1]).write_text(sys.argv[2].replace("\\n", "\n"))
print(Path(sys.argv[1]).read_text())
