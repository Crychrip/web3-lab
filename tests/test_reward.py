from deai.reward import contribution, split_rewards


def test_reward_conservation():
    contrib = {"M1": 7.0, "M2": 7.0, "M3": 6.0}
    rewards = split_rewards(contrib, 100.0)
    assert abs(sum(rewards.values()) - 100.0) < 1e-12
    assert abs(rewards["M1"] - 35.0) < 1e-12
    assert abs(rewards["M3"] - 30.0) < 1e-12


def test_zero_contribution():
    rewards = split_rewards({"M1": 0.0, "M2": 0.0}, 100.0)
    assert rewards == {"M1": 0.0, "M2": 0.0}


def test_equation3_service_weights():
    c = contribution({"text": 10, "image": 5}, {"text": 1.0, "image": 2.0})
    assert c == 20.0
