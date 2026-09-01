from tar_cli.__main__ import build_parser


def test_parser_has_required_commands():
    parser = build_parser()
    names = set()
    for action in parser._subparsers._group_actions:
        names.update(action.choices.keys())
    assert names >= {
        "register",
        "profile",
        "capabilities",
        "discover",
        "verify",
        "swarm-assemble",
    }
