const fs = require("fs");
const path = require("path");
const hre = require("hardhat");
const { ethers, artifacts } = hre;

async function main() {
  const [coordinator] = await ethers.getSigners();
  const Factory = await ethers.getContractFactory("StakingContract");
  const staking = await Factory.deploy(coordinator.address);
  await staking.waitForDeployment();
  const address = await staking.getAddress();

  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  const artifact = await artifacts.readArtifact("StakingContract");
  const payload = {
    address,
    coordinator: coordinator.address,
    abi: artifact.abi,
    network: "localhost",
    chainId: 31337,
  };
  fs.writeFileSync(path.join(outDir, "localhost.json"), JSON.stringify(payload, null, 2));
  console.log("StakingContract", address);
  console.log("coordinator", coordinator.address);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
