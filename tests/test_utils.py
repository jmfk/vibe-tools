from vibe_tools import utils


def test_perform_basic_init_creates_repo_runtime():
    utils.perform_basic_init()

    assert (utils.get_project_root() / ".vibe-tools").exists()
    assert (utils.get_project_root() / ".vibe-tools" / "config.json").exists()
    assert (utils.get_project_root() / ".vibe-tools" / "instructions").exists()


def test_save_memory_writes_instruction_file():
    utils.perform_basic_init()

    path = utils.save_memory("Always run local tests first")

    assert path.exists()
    assert path.read_text() == "Always run local tests first"
    assert path.parent.name == "instructions"


def test_load_config_merges_global_and_local():
    utils.save_config({"default_budget": 10.0}, global_scope=True)
    utils.save_config({"services": {"redis": {"host": "localhost", "port": 6379}}})

    config = utils.load_config()

    assert config["default_budget"] == 10.0
    assert config["services"]["redis"]["port"] == 6379


def test_status_report_uses_repo_local_runtime():
    utils.perform_basic_init()

    report = utils.get_vibe_status_report()

    assert "vibe-tools status" in report
    assert ".vibe-tools" in report
