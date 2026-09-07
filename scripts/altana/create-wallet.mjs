/** Create Altana agent wallet on BNB mainnet. */
import {
  makeWallet,
  writeState,
  readState,
  getNativeBalance,
  explorerAddr,
  BNB,
  CHAIN_NAME,
  CHAIN_ID,
} from "./lib.mjs";

async function main() {
  const existing = readState();
  const { wallet } = await makeWallet();
  const address = wallet.address;
  let balanceEther = "0";
  let funded = false;
  try {
    const bal = await getNativeBalance(address);
    balanceEther = bal.ether;
    funded = bal.funded;
  } catch (e) {
    console.error("balance check failed:", e?.message || e);
  }
  const chainId = BNB?.chainId || BNB?.chain?.id || CHAIN_ID || 56;
  const state = {
    ...(existing || {}),
    chain: CHAIN_NAME,
    chainId,
    walletAddress: address,
    walletExplorer: explorerAddr(address),
    createdAt: existing?.createdAt || new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    funded,
    balanceEther,
    fundHint: "Send BNB to address",
  };
  writeState(state);
  console.log(JSON.stringify({
    ok: true,
    step: "create-wallet",
    walletAddress: address,
    walletExplorer: explorerAddr(address),
    chain: CHAIN_NAME,
    chainId,
    funded,
    balanceEther,
    fundHint: "Send BNB to address",
    stateFile: ".altana-state.json",
    next: funded ? "Run grant then execute" : "Awaiting fund — send BNB to address then status",
  }, null, 2));
}

main().catch((e) => {
  console.error(JSON.stringify({ ok: false, error: String(e?.message || e) }));
  process.exit(1);
});
