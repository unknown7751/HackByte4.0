const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("VolunteerReward", function () {
  let contract;
  let owner;
  let volunteer;
  let stranger;
  const REWARD = ethers.parseEther("0.01");

  beforeEach(async function () {
    [owner, volunteer, stranger] = await ethers.getSigners();

    const VolunteerReward = await ethers.getContractFactory("VolunteerReward");
    contract = await VolunteerReward.deploy(REWARD);
    await contract.waitForDeployment();

    // Fund the contract
    await owner.sendTransaction({
      to: await contract.getAddress(),
      value: ethers.parseEther("1.0"),
    });
  });

  describe("Deployment", function () {
    it("should set the correct owner", async function () {
      expect(await contract.owner()).to.equal(owner.address);
    });

    it("should set the correct reward amount", async function () {
      expect(await contract.rewardAmount()).to.equal(REWARD);
    });

    it("should have received funds", async function () {
      expect(await contract.getBalance()).to.equal(ethers.parseEther("1.0"));
    });
  });

  describe("sendReward", function () {
    it("should send reward to a volunteer", async function () {
      const balanceBefore = await ethers.provider.getBalance(volunteer.address);

      await expect(contract.sendReward(volunteer.address, "task-001"))
        .to.emit(contract, "RewardSent")
        .withArgs(volunteer.address, "task-001", REWARD, await getBlockTimestamp());

      const balanceAfter = await ethers.provider.getBalance(volunteer.address);
      expect(balanceAfter - balanceBefore).to.equal(REWARD);
    });

    it("should mark task as completed", async function () {
      await contract.sendReward(volunteer.address, "task-002");
      expect(await contract.isTaskRewarded("task-002")).to.be.true;
    });

    it("should revert on double-spend (same taskId)", async function () {
      await contract.sendReward(volunteer.address, "task-003");
      await expect(
        contract.sendReward(volunteer.address, "task-003")
      ).to.be.revertedWith("VolunteerReward: task already rewarded");
    });

    it("should revert if caller is not owner", async function () {
      await expect(
        contract.connect(stranger).sendReward(volunteer.address, "task-004")
      ).to.be.revertedWith("VolunteerReward: caller is not the owner");
    });

    it("should revert for zero address", async function () {
      await expect(
        contract.sendReward(ethers.ZeroAddress, "task-005")
      ).to.be.revertedWith("VolunteerReward: zero address");
    });
  });

  describe("Admin functions", function () {
    it("should update reward amount", async function () {
      const newReward = ethers.parseEther("0.05");
      await expect(contract.setRewardAmount(newReward))
        .to.emit(contract, "RewardAmountUpdated")
        .withArgs(REWARD, newReward);
      expect(await contract.rewardAmount()).to.equal(newReward);
    });

    it("should withdraw funds", async function () {
      const contractBalance = await contract.getBalance();
      await expect(contract.withdrawFunds())
        .to.emit(contract, "FundsWithdrawn")
        .withArgs(owner.address, contractBalance);
      expect(await contract.getBalance()).to.equal(0);
    });

    it("should transfer ownership", async function () {
      await contract.transferOwnership(stranger.address);
      expect(await contract.owner()).to.equal(stranger.address);
    });
  });
});

async function getBlockTimestamp() {
  const block = await ethers.provider.getBlock("latest");
  return block.timestamp;
}
