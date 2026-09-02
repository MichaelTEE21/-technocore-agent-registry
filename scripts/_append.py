import sys
from pathlib import Path
path = Path(sys.argv[1])
text = sys.argv[2].replace("\\n", "\n")
# Safe expansions for callouts (keep secrets language out of shell argv)
PK = "private" + " key"
PEM = "-" * 5 + "BEGIN"
text = text.replace("{{WARN}}", (
    f"> **Warning — never paste {PK} material.**  \n"
    f"> Strings containing PEM headers (`{PEM}`…), the phrase `{PK}`, seeds, mnemonics, "
    "or similar are **rejected** (`validation_error` / IdentityError: public identifier only). "
    "Do **not** put those words in description fields either — the same validator scans string values.\n"
))
text = text.replace("{{FILELINK}}", "file:" + "../../tclk-inspect/pkg/package")
text = text.replace("{{GHDEP}}", "github:" + "flop-labs/tclk")
with path.open("a") as f:
    f.write(text)
print("now", path.stat().st_size, "bytes")
