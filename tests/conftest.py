import pytest

from fog_of_love.world import World


@pytest.fixture(scope="session")
def mock_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("run") / "mock-6x4"
    world = World(out_dir=out, model_name="mock", num_agents=6, num_days=4, seed=3)
    summary = world.run()
    return out, summary
