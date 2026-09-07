/** Refresh Altana wallet balance / session status on BNB mainnet */
import {
  publicStatus,
  readState,
  writeState,
  getNativeBalance,
  makeWallet,
  explorerAddr,
  CHAIN_NAME,
  CHAIN_ID,
} from "./lib.mjs";

async function main() {
  let state = readState();
  if (!state?.walletAddress) {
    const { wallet } = await makeWallet();
    state = writeState({
      chain: CHAIN_NAME,
      chainId: CHAIN_ID,
      walletAddress: wallet.address,
      walletExplorer: explorerAddr(wallet.address),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      funded: false,
      balanceEther: "0",
      fundHint: "Send BNB to address",
    });
  }
  try {
    const bal = await getNativeBalance(state.walletAddress);
    state = writeState({
      ...state,
      funded: bal.funded,
      balanceEther: bal.ether,
      updatedAt: new Date().toISOString(),
    });
  } catch (e) {
    console.error("balance refresh failed:", e?.message || e);
  }
  console.log(JSON.stringify(publicStatus(), null, 2));
}

main().catch((e) => {
  console.error(JSON.stringify({ ok: false, error: String(e?.message || e) }));
  process.exit(1);
});
