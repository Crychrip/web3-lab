const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("StakingContract", function () {
  async function deploy() {
    const [coordinator, c1, c2, c3, miner, other] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("StakingContract");
    const staking = await Factory.deploy(coordinator.address);
    await staking.waitForDeployment();
    return { staking, coordinator, c1, c2, c3, miner, other };
  }

  it("weightOf is 0 before lock", async function () {
    const { staking, c1 } = await deploy();
    expect(await staking.weightOf(c1.address)).to.equal(0);
    expect(await staking.validPass(c1.address)).to.equal(false);
  });

  it("lock 100/300/600 native yields effective stakes 100/300/600", async function () {
    const { staking, c1, c2, c3 } = await deploy();
    for (const [acct, amount] of [
      [c1, 100],
      [c2, 300],
      [c3, 600],
    ]) {
      await staking.connect(acct).faucet(amount);
      await staking.connect(acct).lock(amount, true);
    }
    expect(await staking.weightOf(c1.address)).to.equal(100);
    expect(await staking.weightOf(c2.address)).to.equal(300);
    expect(await staking.weightOf(c3.address)).to.equal(600);
    expect(await staking.validPass(c1.address)).to.equal(true);
    expect(await staking.totalLocked()).to.equal(1000);
  });

  it("other-asset lock uses q=0.1", async function () {
    const { staking, c1 } = await deploy();
    await staking.connect(c1).faucet(110);
    await staking.connect(c1).lock(100, true);
    await staking.connect(c1).lock(10, false);
    expect(await staking.weightOf(c1.address)).to.equal(101); // 100 + floor(10*1/10)
  });

  it("unlock restores wallet and clears pass", async function () {
    const { staking, c1 } = await deploy();
    await staking.connect(c1).faucet(100);
    await staking.connect(c1).lock(100, true);
    await staking.connect(c1).unlock();
    expect(await staking.wallet(c1.address)).to.equal(100);
    expect(await staking.weightOf(c1.address)).to.equal(0);
    expect(await staking.validPass(c1.address)).to.equal(false);
    expect(await staking.totalLocked()).to.equal(0);
  });

  it("unlock reverts when nothing is locked", async function () {
    const { staking, c1 } = await deploy();
    await expect(staking.connect(c1).unlock()).to.be.revertedWithCustomError(
      staking,
      "NothingLocked"
    );
  });

  it("lock reverts without balance", async function () {
    const { staking, c1 } = await deploy();
    await expect(staking.connect(c1).lock(1, true)).to.be.revertedWithCustomError(
      staking,
      "InsufficientBalance"
    );
  });

  it("chargedPay integer fee: price 100 -> miner 95, fee 5", async function () {
    const { staking, c1, miner } = await deploy();
    await staking.connect(c1).faucet(100);
    await staking.connect(c1).chargedPay(miner.address, 100);
    expect(await staking.wallet(c1.address)).to.equal(0);
    expect(await staking.minerRewards(miner.address)).to.equal(95);
    expect(await staking.coordinatorFees()).to.equal(5);
  });

  it("only coordinator can creditReward", async function () {
    const { staking, c1, miner } = await deploy();
    await expect(
      staking.connect(c1).creditReward(miner.address, 10)
    ).to.be.revertedWithCustomError(staking, "NotCoordinator");
  });

  it("creditReward accumulates miner balance", async function () {
    const { staking, coordinator, miner } = await deploy();
    await staking.connect(coordinator).creditReward(miner.address, 35);
    await staking.connect(coordinator).creditReward(miner.address, 15);
    expect(await staking.minerRewards(miner.address)).to.equal(50);
  });

  it("invariant: totalLocked equals sum of native+other after random lock/unlock", async function () {
    const { staking, c1, c2 } = await deploy();
    await staking.connect(c1).faucet(10_000);
    await staking.connect(c2).faucet(10_000);

    const actions = [
      async () => staking.connect(c1).lock(100, true),
      async () => staking.connect(c2).lock(300, true),
      async () => staking.connect(c1).lock(50, false),
      async () => staking.connect(c1).unlock(),
      async () => staking.connect(c2).lock(200, false),
      async () => staking.connect(c2).unlock(),
      async () => staking.connect(c1).lock(80, true),
    ];
    for (const act of actions) {
      await act();
      const t = await staking.totalLocked();
      const s1n = await staking.nativeLocked(c1.address);
      const s1o = await staking.otherLocked(c1.address);
      const s2n = await staking.nativeLocked(c2.address);
      const s2o = await staking.otherLocked(c2.address);
      expect(t).to.equal(s1n + s1o + s2n + s2o);
    }
  });
});
