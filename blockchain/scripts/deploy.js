/**
 * Deploy VolunteerReward to Polygon Amoy (or local Hardhat node).
 *
 * Usage:
 *   npx hardhat run scripts/deploy.js --network amoy
 */
const hre = require("hardhat");
const { ethers } = hre;

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("─────────────────────────────────────────");
  console.log("Deploying VolunteerReward contract...");
  console.log("Deployer address :", deployer.address);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log("Deployer balance :", ethers.formatEther(balance), "MATIC");

  // Default reward: 0.01 MATIC (in wei)
  const rewardAmount = ethers.parseEther("0.01");

  // Deploy
  const VolunteerReward = await ethers.getContractFactory("VolunteerReward");
  const contract = await VolunteerReward.deploy(rewardAmount);
  await contract.waitForDeployment();

  const contractAddress = await contract.getAddress();
  console.log("─────────────────────────────────────────");
  console.log("✅ VolunteerReward deployed to:", contractAddress);
  console.log("   Reward amount:", ethers.formatEther(rewardAmount), "MATIC");

  // Fund the contract with 0.1 MATIC so it can send rewards
  const fundAmount = ethers.parseEther("0.1");
  console.log("\nFunding contract with", ethers.formatEther(fundAmount), "MATIC...");

  const tx = await deployer.sendTransaction({
    to: contractAddress,
    value: fundAmount,
  });
  await tx.wait();

  const contractBalance = await ethers.provider.getBalance(contractAddress);
  console.log("✅ Contract balance:", ethers.formatEther(contractBalance), "MATIC");

  console.log("\n─────────────────────────────────────────");
  console.log("📋 NEXT STEPS:");
  console.log("1. Copy the contract address above");
  console.log("2. Set REWARD_CONTRACT_ADDRESS=" + contractAddress + " in your .env");
  console.log("3. Get the ABI from blockchain/artifacts/contracts/VolunteerReward.sol/VolunteerReward.json");
  console.log("─────────────────────────────────────────");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
