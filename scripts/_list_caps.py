import sys
sys.path.insert(0, "src")
from tar.taxonomy import list_capabilities
print([c["id"] for c in list_capabilities()][:40])
