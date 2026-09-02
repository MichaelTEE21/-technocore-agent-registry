from pathlib import Path

readme = Path("README.md")
rt = readme.read_text()
needle = "Further reading: [architecture](docs/architecture.md)"
insert = "Further reading: [**Agent registration guide**](docs/AGENT_REGISTRATION_GUIDE.md) · [architecture](docs/architecture.md)"
if "AGENT_REGISTRATION_GUIDE" not in rt:
    assert needle in rt
    rt = rt.replace(needle, insert, 1)
marker = "- Developers: http://127.0.0.1:8080/ui/developers\n"
add = marker + "- Agent registration guide (repo): docs/AGENT_REGISTRATION_GUIDE.md\n"
if "Agent registration guide (repo)" not in rt:
    assert marker in rt
    rt = rt.replace(marker, add, 1)
readme.write_text(rt)
print("README ok")

base = Path("src/tar/templates/base.html")
bt = base.read_text()
if "Agent registration guide" not in bt:
    needle = "legal capabilities are research terminology only\n    </footer>"
    repl = (
        "legal capabilities are research terminology only ·\n"
        "      <a href=\"/ui/developers\">Agent registration guide</a> "
        "(see docs/AGENT_REGISTRATION_GUIDE.md)\n"
        "    </footer>"
    )
    assert needle in bt
    base.write_text(bt.replace(needle, repl, 1))
print("base ok")

idx = Path("src/tar/templates/index.html")
it = idx.read_text()
if "Agent registration guide" not in it:
    old = '      <a class="text-link" href="/ui/discover">Discover</a>\n'
    new = old + '      <a class="text-link" href="/ui/developers">Agent registration guide</a>\n'
    assert old in it
    idx.write_text(it.replace(old, new, 1))
print("index ok")

dev = Path("src/tar/templates/developers.html")
dt = dev.read_text()
if "AGENT_REGISTRATION_GUIDE" not in dt:
    dt = dt.replace(
        "<h1>TarClient</h1>",
        "<h1>TarClient</h1>\n"
        "<p class=\"note\"><strong>Agent registration guide:</strong> "
        "<code>docs/AGENT_REGISTRATION_GUIDE.md</code> "
        "(identity, UI/API register, Communicate, tclk/1, troubleshooting). "
        "Screenshots: <code>docs/guide-assets/</code>.</p>",
        1,
    )
    dev.write_text(dt)
print("developers ok")
