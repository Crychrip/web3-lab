const { ethers } = require("hardhat");

async function main() {
  const [coordinator, c1, c2, c3, miner] = await ethers.getSigners();
  const Factory = await ethers.getContractFactory("StakingContract");
  const staking = await Factory.deploy(coordinator.address);
  await staking.waitForDeployment();
  const addr = await staking.getAddress();
  console.log(`deployed ${addr}`);
  console.log("step,action,account,detail,weight,totalLocked,wallet");

  async function row(step, action, account, detail) {
    const weight = await staking.weightOf(account.address);
    const locked = await staking.totalLocked();
    const wallet = await staking.wallet(account.address);
    console.log(
      `${step},${action},${account.address.slice(0, 8)},${detail},${weight},${locked},${wallet}`
    );
  }

  let step = 1;
  await staking.connect(c1).faucet(1000);
  await row(step++, "faucet", c1, "1000");
  await staking.connect(c2).faucet(1000);
  await row(step++, "faucet", c2, "1000");
  await staking.connect(c3).faucet(1000);
  await row(step++, "faucet", c3, "1000");

  await staking.connect(c1).lock(100, true);
  await row(step++, "lockNative", c1, "100");
  await staking.connect(c2).lock(300, true);
  await row(step++, "lockNative", c2, "300");
  await staking.connect(c3).lock(600, true);
  await row(step++, "lockNative", c3, "600");

  await staking.connect(c1).lock(20, false);
  await row(step++, "lockOther", c1, "20"); // +2 weight
  await staking.connect(c2).lock(10, false);
  await row(step++, "lockOther", c2, "10"); // +1 weight

  console.log(
    `weights,C1=${await staking.weightOf(c1.address)},C2=${await staking.weightOf(c2.address)},C3=${await staking.weightOf(c3.address)}`
  );

  await staking.connect(c1).unlock();
  await row(step++, "unlock", c1, "all");
  await staking.connect(c1).faucet(100);
  await row(step++, "faucet", c1, "100");
  await staking.connect(c1).lock(100, true);
  await row(step++, "lockNative", c1, "100");

  await staking.connect(c3).chargedPay(miner.address, 100);
  await row(step++, "chargedPay", c3, "price=100");
  console.log(
    `afterPay,minerRewards=${await staking.minerRewards(miner.address)},fee=${await staking.coordinatorFees()}`
  );

  await staking.connect(coordinator).creditReward(miner.address, 35);
  await row(step++, "creditReward", coordinator, "miner+35");

  await staking.connect(c2).unlock();
  await row(step++, "unlock", c2, "all");
  await staking.connect(c2).lock(300, true);
  await row(step++, "lockNative", c2, "300");
  await staking.connect(c3).unlock();
  await row(step++, "unlock", c3, "all");
  await staking.connect(c3).lock(600, true);
  await row(step++, "lockNative", c3, "600");

  await staking.connect(coordinator).creditReward(miner.address, 15);
  await row(step++, "creditReward", coordinator, "miner+15");

  console.log(`calls=${step - 1}`);
  console.log(
    `final,C1=${await staking.weightOf(c1.address)},C2=${await staking.weightOf(c2.address)},C3=${await staking.weightOf(c3.address)},totalLocked=${await staking.totalLocked()},minerRewards=${await staking.minerRewards(miner.address)}`
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
