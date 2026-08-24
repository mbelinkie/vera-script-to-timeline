from vera_timeline_agent import tooling_package_name


def test_python_package_can_be_imported() -> None:
    assert tooling_package_name() == "vera-timeline-agent"
